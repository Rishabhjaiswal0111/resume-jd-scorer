from app.pipeline.pros_cons import derive_pros_cons
from app.pipeline.scoring_math import compute_score
from app.schemas.evaluation import CoreRequirementAssessment, CriterionResult, RoleOverlap
from app.schemas.rubric import Criterion


def crit(key: str, operator: str, importance: str = "normal") -> Criterion:
    return Criterion.model_validate(
        {
            "key": key,
            "name": key,
            "attribute": "other",
            "operator": operator,
            "importance": importance,
            "values": [],
            "source_excerpt": "",
        }
    )


def res(key: str, outcome: str, evidence: str = "evidenced") -> CriterionResult:
    return CriterionResult.model_validate(
        {
            "key": key,
            "candidate_value": "",
            "evidence_strength": evidence,
            "outcome": outcome,
            "reasoning": f"why {key}",
        }
    )


def run(rubric: list[Criterion], results: list[CriterionResult], role: str, core: str):  # type: ignore[no-untyped-def]
    by_key = {r.key: r for r in results}
    scored = compute_score(rubric, by_key, role, core).criteria  # type: ignore[arg-type]
    return derive_pros_cons(
        scored,
        {k: r.reasoning for k, r in by_key.items()},
        RoleOverlap(level=role, summary="role summary"),  # type: ignore[arg-type]
        CoreRequirementAssessment(level=core, summary="core summary"),  # type: ignore[arg-type]
    )


def test_split_and_order() -> None:
    rubric = [
        crit("c_nice", "nice_to_have"),
        crit("c_pref", "preferred"),
        crit("c_must_normal", "must_have"),
        crit("c_must_high", "must_have", "high"),
    ]
    results = [
        res("c_nice", "Full Pass"),
        res("c_pref", "Partial Pass"),
        res("c_must_normal", "Full Pass"),
        res("c_must_high", "Fail"),
    ]
    pc = run(rubric, results, "Strong", "Partial")

    # Strong role overlap has no cap -> pro; Partial core carries a cap (79) -> con.
    assert [p.source for p in pc.pros] == ["role_overlap", "c_must_normal", "c_nice"]
    assert [c.source for c in pc.cons] == ["core_requirement", "c_must_high", "c_pref"]
    assert pc.pros[1].text == "why c_must_normal"


def test_forced_fail_becomes_a_con() -> None:
    rubric = [crit("c_a", "must_have", "high")]
    pc = run(rubric, [res("c_a", "Full Pass", "not_evidenced")], "Strong", "Clear")
    assert [c.source for c in pc.cons] == ["c_a"]
    assert pc.cons[0].outcome == "Fail"


def test_as_json_round_trip() -> None:
    pc = run([crit("c_a", "preferred")], [res("c_a", "Full Pass")], "None", "Clear")
    pros, cons = pc.as_json()
    assert pros[0] == {
        "text": "core summary",
        "source": "core_requirement",
        "operator": None,
        "importance": None,
        "outcome": "Clear",
    }
    assert [c["source"] for c in cons] == ["role_overlap"]


def test_absent_red_flag_is_not_a_strength_but_a_present_one_is_a_concern() -> None:
    rubric = [
        crit("c_skill", "must_have"),
        crit("c_avoid_a", "must_avoid"),
        crit("c_avoid_b", "must_avoid"),
    ]
    results = [
        res("c_skill", "Full Pass"),
        res("c_avoid_a", "Full Pass", "not_evidenced"),  # red flag absent
        res("c_avoid_b", "Fail", "evidenced"),  # red flag present
    ]
    pc = run(rubric, results, "Strong", "Clear")
    assert [p.source for p in pc.pros] == ["role_overlap", "core_requirement", "c_skill"]
    assert [c.source for c in pc.cons] == ["c_avoid_b"]
