"""Table-driven tests for the score math (PLAN.md §7). Expected values are hand-computed."""

import itertools
import json
from decimal import Decimal

import pytest

from app.pipeline.scoring_math import (
    ENGINE_VERSION,
    ScoringConfig,
    compute_score,
    split_bucket_weight,
)
from app.schemas.evaluation import CriterionResult
from app.schemas.rubric import Criterion


def crit(key: str, operator: str, importance: str = "normal") -> Criterion:
    return Criterion.model_validate(
        {
            "key": key,
            "name": key,
            "attribute": "hard_skills",
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
            "reasoning": f"{key} {outcome}",
        }
    )


# must_have: a (high) + b (normal) -> 45 split 2:1 = 30 / 15. preferred: c -> 20.
# nice_to_have (5) + must_avoid (10) + may_avoid (0) are empty -> forfeited 15, denominator 85.
BASE = [crit("c_a", "must_have", "high"), crit("c_b", "must_have"), crit("c_c", "preferred")]


def score(results: list[CriterionResult], role: str = "Strong", core: str = "Clear", **cfg: bool):  # type: ignore[no-untyped-def]
    return compute_score(
        BASE,
        {r.key: r for r in results},
        role,
        core,
        ScoringConfig(**cfg),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("results", "role", "core", "expected"),
    [
        # all pass: 30+15+20+10+10 = 85 / 85 -> 100
        (
            [res("c_a", "Full Pass"), res("c_b", "Full Pass"), res("c_c", "Full Pass")],
            "Strong",
            "Clear",
            "100.00",
        ),
        # 30 + 7.5 + 0 + 10 + 10 = 57.5 / 85 * 100 = 67.647... -> 67.65
        (
            [res("c_a", "Full Pass"), res("c_b", "Partial Pass"), res("c_c", "Fail")],
            "Strong",
            "Clear",
            "67.65",
        ),
        # role Moderate: 30+15+20+5+10 = 80 / 85 = 94.12 -> capped 79
        (
            [res("c_a", "Full Pass"), res("c_b", "Full Pass"), res("c_c", "Full Pass")],
            "Moderate",
            "Clear",
            "79.00",
        ),
        # role Moderate (cap 79) + core Weak (cap 59):
        # 30+15+20+5+2.5 = 72.5/85 = 85.29 -> lowest cap 59
        (
            [res("c_a", "Full Pass"), res("c_b", "Full Pass"), res("c_c", "Full Pass")],
            "Moderate",
            "Weak",
            "59.00",
        ),
        # core None -> cap 49; earned 30+15+20+10+0 = 75/85 = 88.2 -> 49
        (
            [res("c_a", "Full Pass"), res("c_b", "Full Pass"), res("c_c", "Full Pass")],
            "Strong",
            "None",
            "49.00",
        ),
        # cap not binding: role Weak (cap 59), earned 0+0+0+2.5+10 = 12.5/85 = 14.71, then
        # high must_have c_a failed -> -30 -> clamped to 0
        ([res("c_a", "Fail"), res("c_b", "Fail"), res("c_c", "Fail")], "Weak", "Clear", "0.00"),
    ],
)
def test_score_table(results: list[CriterionResult], role: str, core: str, expected: str) -> None:
    assert score(results, role, core).score == Decimal(expected)


def test_force_fail_on_must_have_without_evidence_and_penalty() -> None:
    # c_a: LLM said Partial Pass but evidence not_evidenced -> forced Fail (earned 0).
    # earned 0 + 15 + 20 + 10 + 10 = 55 / 85 * 100 = 64.70588...; high must_have failed -> -30
    # = 34.70588... -> 34.71
    result = score(
        [
            res("c_a", "Partial Pass", "not_evidenced"),
            res("c_b", "Full Pass"),
            res("c_c", "Full Pass"),
        ]
    )
    assert result.score == Decimal("34.71")
    a = next(s for s in result.criteria if s.key == "c_a")
    assert (a.llm_outcome, a.outcome, a.was_forced_fail, a.earned) == (
        "Partial Pass",
        "Fail",
        True,
        0,
    )
    assert result.breakdown["penalty"] == {"applied": True, "points": "30", "triggered_by": ["c_a"]}


def test_contradicted_must_have_is_forced_fail() -> None:
    result = score(
        [res("c_a", "Full Pass"), res("c_b", "Full Pass", "contradicted"), res("c_c", "Fail")]
    )
    b = next(s for s in result.criteria if s.key == "c_b")
    assert b.outcome == "Fail" and b.was_forced_fail
    # normal-importance must_have failing does not trigger the penalty:
    # 30 + 0 + 0 + 20 = 50 / 85 = 58.82
    assert result.breakdown["penalty"]["applied"] is False
    assert result.score == Decimal("58.82")


def test_llm_fail_without_evidence_is_not_flagged_as_forced() -> None:
    result = score(
        [res("c_a", "Fail", "not_evidenced"), res("c_b", "Full Pass"), res("c_c", "Full Pass")]
    )
    a = next(s for s in result.criteria if s.key == "c_a")
    assert a.outcome == "Fail" and not a.was_forced_fail


def test_penalty_can_be_disabled() -> None:
    results = [res("c_a", "Fail"), res("c_b", "Full Pass"), res("c_c", "Full Pass")]
    # 0 + 15 + 20 + 10 + 10 = 55 / 85 = 64.71
    assert score(results, hard_fail_penalty=False).score == Decimal("64.71")
    assert score(results).score == Decimal("34.71")


def test_must_avoid_passes_when_absent() -> None:
    rubric = [crit("c_x", "must_have"), crit("c_avoid", "must_avoid")]
    results = {
        "c_x": res("c_x", "Full Pass"),
        "c_avoid": res("c_avoid", "Fail", "not_evidenced"),  # LLM inverted semantics
    }
    result = compute_score(rubric, results, "Strong", "Clear")
    avoid = next(s for s in result.criteria if s.key == "c_avoid")
    assert (avoid.outcome, avoid.forced) == ("Full Pass", "pass_absent")
    # forfeited preferred 20 + nice 5 + may_avoid 0 = 25 -> denominator 75; earned 45+10+10+10 = 75
    assert result.score == Decimal("100.00")


def test_must_avoid_already_passing_is_not_flagged() -> None:
    rubric = [crit("c_x", "must_have"), crit("c_avoid", "must_avoid")]
    results = {
        "c_x": res("c_x", "Full Pass"),
        "c_avoid": res("c_avoid", "Full Pass", "not_evidenced"),
    }
    avoid = next(
        s for s in compute_score(rubric, results, "Strong", "Clear").criteria if s.key == "c_avoid"
    )
    assert (avoid.outcome, avoid.forced) == ("Full Pass", None)


def test_must_avoid_present_fails() -> None:
    rubric = [crit("c_x", "must_have"), crit("c_avoid", "must_avoid")]
    results = {"c_x": res("c_x", "Full Pass"), "c_avoid": res("c_avoid", "Fail", "evidenced")}
    # earned 45 + 0 + 10 + 10 = 65 / 75 = 86.666... -> 86.67
    assert compute_score(rubric, results, "Strong", "Clear").score == Decimal("86.67")


def test_may_avoid_has_zero_weight() -> None:
    rubric = [crit("c_x", "must_have"), crit("c_m", "may_avoid")]
    results = {"c_x": res("c_x", "Full Pass"), "c_m": res("c_m", "Fail")}
    result = compute_score(rubric, results, "Strong", "Clear")
    assert result.score == Decimal("100.00")
    assert next(s for s in result.criteria if s.key == "c_m").weight == 0


@pytest.mark.parametrize(
    ("weight", "importances", "expected"),
    [
        ("45", ["high", "normal"], ["30.00", "15.00"]),
        # 20/3 = 6.67 x3 = 20.01 -> drift -0.01 to first item (no high item)
        ("20", ["normal"] * 3, ["6.66", "6.67", "6.67"]),
        # factors 1x6 + 2 = 8: 45/8 = 5.625 -> 5.63 (x6 = 33.78) and high 11.25 -> sum 45.03,
        # drift -0.03 goes to the first HIGH item -> 11.22
        (
            "45",
            ["normal", "normal", "high", "normal", "normal", "normal", "normal"],
            ["5.63", "5.63", "11.22", "5.63", "5.63", "5.63", "5.63"],
        ),
        ("10", ["high"], ["10"]),
        ("0", ["normal", "normal"], ["0.00", "0.00"]),
        ("5", [], []),
    ],
)
def test_split_bucket_weight(weight: str, importances: list[str], expected: list[str]) -> None:
    shares = split_bucket_weight(Decimal(weight), importances)
    assert shares == [Decimal(e) for e in expected]
    if importances:
        assert sum(shares) == Decimal(weight)


def test_missing_result_is_rejected() -> None:
    with pytest.raises(ValueError, match="c_c"):
        compute_score(
            BASE, {"c_a": res("c_a", "Fail"), "c_b": res("c_b", "Fail")}, "Strong", "Clear"
        )


def test_breakdown_is_json_serialisable_and_complete() -> None:
    result = score(
        [res("c_a", "Full Pass"), res("c_b", "Partial Pass"), res("c_c", "Fail")], "Moderate"
    )
    bd = json.loads(json.dumps(result.breakdown))
    assert bd["engine_version"] == ENGINE_VERSION == result.engine_version
    assert bd["forfeited_weight"] == "15"
    assert bd["denominator"] == "85"
    assert bd["final_score"] == str(result.score)
    assert [b["bucket"] for b in bd["buckets"]] == [
        "must_have",
        "preferred",
        "nice_to_have",
        "must_avoid",
        "may_avoid",
    ]
    assert bd["caps"]["triggered"] == [{"source": "role_overlap", "level": "Moderate", "cap": "79"}]
    # 30 + 7.5 + 0 + 5 + 10 = 52.5 / 85 = 61.76 -> cap 79 not binding
    assert bd["caps"]["binding"] is False
    assert result.score == Decimal("61.76")


def test_deterministic_and_bounded_over_all_outcome_combinations() -> None:
    outcomes = ["Full Pass", "Partial Pass", "Fail"]
    evidence = ["evidenced", "not_evidenced"]
    for combo in itertools.product(
        outcomes, evidence, outcomes, outcomes, ["Strong", "None"], ["Clear", "Weak"]
    ):
        oa, ea, ob, oc, role, core = combo
        results = [res("c_a", oa, ea), res("c_b", ob), res("c_c", oc)]
        first = score(results, role, core)
        assert first.score == score(results, role, core).score
        assert Decimal(0) <= first.score <= Decimal(100)
