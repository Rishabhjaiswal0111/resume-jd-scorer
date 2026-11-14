"""Engine 1.1.0 rules: screening unknowns, group relief, knock-outs, verdicts.

Expected values are hand-computed in the comments.
"""

from decimal import Decimal

from app.pipeline.pros_cons import derive_pros_cons
from app.pipeline.scoring_math import compute_score
from app.schemas.evaluation import CoreRequirementAssessment, CriterionResult, RoleOverlap
from app.schemas.rubric import Criterion


def crit(
    key: str, operator: str = "must_have", importance: str = "normal", **extra: object
) -> Criterion:
    return Criterion.model_validate(
        {
            "key": key,
            "name": key,
            "attribute": "other",
            "operator": operator,
            "importance": importance,
            "values": [],
            "source_excerpt": "",
            **extra,
        }
    )


def res(key: str, outcome: str, evidence: str = "evidenced") -> CriterionResult:
    return CriterionResult.model_validate(
        {
            "key": key,
            "candidate_value": "",
            "evidence_strength": evidence,
            "outcome": outcome,
            "reasoning": key,
        }
    )


def run(
    rubric: list[Criterion],
    results: list[CriterionResult],
    role: str = "Strong",
    core: str = "Clear",
):  # type: ignore[no-untyped-def]
    return compute_score(rubric, {r.key: r for r in results}, role, core)  # type: ignore[arg-type]


def test_silent_screening_criterion_is_unknown_and_excluded() -> None:
    rubric = [crit("c_skill"), crit("c_relocate", verify_in_screening=True)]
    result = run(rubric, [res("c_skill", "Full Pass"), res("c_relocate", "Fail", "not_evidenced")])
    reloc = next(s for s in result.criteria if s.key == "c_relocate")
    assert (reloc.outcome, reloc.weight, reloc.forced) == ("Unknown", 0, "unknown_screen")
    # must_have 45 goes entirely to c_skill; forfeited 20+5+10+0 = 35 -> denominator 65;
    # earned 45 + 10 + 10 = 65 -> 100
    assert result.score == Decimal("100.00")
    assert result.screening == ["c_relocate"]
    assert result.breakdown["buckets"][0]["unknown"] == 1


def test_screening_criterion_with_evidence_is_graded_normally() -> None:
    rubric = [crit("c_skill"), crit("c_relocate", verify_in_screening=True)]
    result = run(rubric, [res("c_skill", "Full Pass"), res("c_relocate", "Fail", "contradicted")])
    reloc = next(s for s in result.criteria if s.key == "c_relocate")
    assert reloc.outcome == "Fail"
    assert result.screening == []
    # 22.5 + 0 + 10 + 10 = 42.5 / 65 = 65.38
    assert result.score == Decimal("65")


def test_bucket_of_only_unknowns_is_forfeited() -> None:
    rubric = [crit("c_skill"), crit("c_notice", "preferred", verify_in_screening=True)]
    result = run(rubric, [res("c_skill", "Full Pass"), res("c_notice", "Fail", "not_evidenced")])
    preferred = next(b for b in result.breakdown["buckets"] if b["bucket"] == "preferred")
    assert preferred["forfeited"] is True
    assert result.score == Decimal("100.00")


def test_group_loses_only_its_biggest_miss() -> None:
    # must_have: c_core (high) 22.5, c_ecom 11.25, c_pay 11.25 (same group "domain")
    rubric = [
        crit("c_core", importance="high"),
        crit("c_ecom", group="domain"),
        crit("c_pay", group="domain"),
    ]
    result = run(rubric, [res("c_core", "Full Pass"), res("c_ecom", "Fail"), res("c_pay", "Fail")])
    # losses 11.25 + 11.25 = 22.5; group keeps only the biggest (11.25): relief 11.25
    assert result.breakdown["group_adjustments"] == [
        {"group": "domain", "criteria": ["c_ecom", "c_pay"], "relief": "11.25"}
    ]
    # earned 22.5 + 11.25 relief + 10 + 10 = 53.75 / 65 = 82.69
    assert result.score == Decimal("83")


def test_single_member_group_gets_no_relief() -> None:
    rubric = [crit("c_core"), crit("c_ecom", group="domain")]
    result = run(rubric, [res("c_core", "Full Pass"), res("c_ecom", "Fail")])
    assert result.breakdown["group_adjustments"] == []


def test_failed_knockout_caps_and_marks_not_eligible() -> None:
    rubric = [crit("c_skill", importance="high"), crit("c_auth", knockout=True)]
    result = run(rubric, [res("c_skill", "Full Pass"), res("c_auth", "Fail", "contradicted")])
    # 30 + 0 + 10 + 10 = 50 / 65 = 76.92 -> knockout cap 49
    assert result.score == Decimal("49.00")
    assert result.verdict == "Not eligible"
    assert result.breakdown["knockouts_failed"] == ["c_auth"]


def test_verdict_tiers() -> None:
    rubric = [crit("c_a"), crit("c_b")]
    strong = run(rubric, [res("c_a", "Full Pass"), res("c_b", "Full Pass")])
    possible = run(rubric, [res("c_a", "Full Pass"), res("c_b", "Fail")])
    weak = run(rubric, [res("c_a", "Fail"), res("c_b", "Fail")], role="Weak", core="Weak")
    assert (strong.score, strong.verdict) == (Decimal("100.00"), "Strong fit")
    # 22.5 + 20 = 42.5 / 65 = 65.38
    assert (possible.score, possible.verdict) == (Decimal("65"), "Possible fit")
    # 0 + 2.5 + 2.5 = 5 / 65 = 7.69
    assert (weak.score, weak.verdict) == (Decimal("8"), "Weak fit")


def test_unknown_criteria_are_not_pros_or_cons() -> None:
    rubric = [crit("c_skill"), crit("c_relocate", verify_in_screening=True)]
    results = [res("c_skill", "Full Pass"), res("c_relocate", "Fail", "not_evidenced")]
    scored = run(rubric, results).criteria
    pc = derive_pros_cons(
        scored,
        {r.key: r.reasoning for r in results},
        RoleOverlap(level="Strong", summary="r"),
        CoreRequirementAssessment(level="Clear", summary="c"),
    )
    sources = [p.source for p in pc.pros + pc.cons]
    assert "c_relocate" not in sources


def test_v1_rubric_without_new_fields_still_scores() -> None:
    legacy = Criterion.model_validate(
        {
            "key": "c_x",
            "name": "x",
            "attribute": "other",
            "operator": "must_have",
            "importance": "normal",
            "values": [],
            "source_excerpt": "",
        }
    )
    assert (legacy.knockout, legacy.verify_in_screening, legacy.group) == (False, False, "")
    assert run([legacy], [res("c_x", "Full Pass")]).score == Decimal("100.00")


def test_final_score_is_a_whole_number_rounded_half_up() -> None:
    # must_have 45 (Full) + nice_to_have 5 (Full) + must_avoid 0 (present -> Fail) + 10 + 10
    # = 70; preferred forfeited (20) -> denominator 80; 70 / 80 = 87.5 exactly -> 88
    rubric = [crit("c_a"), crit("c_n", "nice_to_have"), crit("c_v", "must_avoid")]
    result = run(rubric, [res("c_a", "Full Pass"), res("c_n", "Full Pass"), res("c_v", "Fail")])
    assert Decimal(result.breakdown["raw_score"]) == Decimal("87.5")
    assert result.score == Decimal(88)
    assert str(result.score) == "88"
    assert result.engine_version == "1.2.0"
