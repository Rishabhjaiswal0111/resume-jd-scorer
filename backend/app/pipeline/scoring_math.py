"""Deterministic score computation (PLAN.md §7, docs/scoring-spec.md).

PURE: no I/O, no DB, no clock, no randomness. Same inputs => same output, forever.
All arithmetic is Decimal. Any behaviour change here MUST bump ENGINE_VERSION.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.schemas.evaluation import CoreLevel, CriterionResult, Outcome, RoleOverlapLevel
from app.schemas.rubric import OPERATORS, Criterion, Operator

ENGINE_VERSION = "1.0.0"

BUCKET_WEIGHTS: Mapping[str, Decimal] = {
    "must_have": Decimal(45),
    "preferred": Decimal(20),
    "nice_to_have": Decimal(5),
    "must_avoid": Decimal(10),
    "may_avoid": Decimal(0),
    "role_overlap": Decimal(10),
    "core_requirement": Decimal(10),
}
IMPORTANCE_FACTORS: Mapping[str, Decimal] = {"high": Decimal(2), "normal": Decimal(1)}

OUTCOME_PCT: Mapping[Outcome, Decimal] = {
    "Full Pass": Decimal(100),
    "Partial Pass": Decimal(50),
    "Fail": Decimal(0),
}
ROLE_OVERLAP_PCT: Mapping[RoleOverlapLevel, Decimal] = {
    "Strong": Decimal(100),
    "Moderate": Decimal(50),
    "Weak": Decimal(25),
    "None": Decimal(0),
}
CORE_PCT: Mapping[CoreLevel, Decimal] = {
    "Clear": Decimal(100),
    "Partial": Decimal(50),
    "Weak": Decimal(25),
    "None": Decimal(0),
}
ROLE_OVERLAP_CAP: Mapping[RoleOverlapLevel, Decimal] = {
    "None": Decimal(49),
    "Weak": Decimal(59),
    "Moderate": Decimal(79),
}
CORE_CAP: Mapping[CoreLevel, Decimal] = {
    "None": Decimal(49),
    "Weak": Decimal(59),
    "Partial": Decimal(79),
}
HARD_FAIL_PENALTY = Decimal(30)
NO_EVIDENCE = ("not_evidenced", "contradicted")

_CENT = Decimal("0.01")
_HUNDRED = Decimal(100)


def _r2(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ScoringConfig:
    hard_fail_penalty: bool = True


@dataclass(frozen=True)
class ScoredCriterion:
    key: str
    operator: Operator
    importance: str
    llm_outcome: Outcome
    outcome: Outcome
    evidence_strength: str
    forced: str | None  # "fail_no_evidence" | "pass_absent" | None
    weight: Decimal
    earned: Decimal

    @property
    def was_forced_fail(self) -> bool:
        return self.forced == "fail_no_evidence"


@dataclass(frozen=True)
class ScoreResult:
    score: Decimal
    criteria: list[ScoredCriterion]
    breakdown: dict[str, Any] = field(default_factory=dict)
    engine_version: str = ENGINE_VERSION


def split_bucket_weight(bucket_weight: Decimal, importances: Sequence[str]) -> list[Decimal]:
    """Split a bucket's weight across its criteria by importance (high=2, normal=1).

    Each share is rounded to 2 dp; the rounding drift goes to the first high-importance
    item (or the first item if none is high), so shares always sum to the bucket weight.
    """
    if not importances:
        return []
    factors = [IMPORTANCE_FACTORS[i] for i in importances]
    total = sum(factors, Decimal(0))
    shares = [_r2(bucket_weight * f / total) for f in factors]
    drift = bucket_weight - sum(shares, Decimal(0))
    if drift:
        target = next((i for i, imp in enumerate(importances) if imp == "high"), 0)
        shares[target] += drift
    return shares


def _apply_force_rules(criterion: Criterion, result: CriterionResult) -> tuple[Outcome, str | None]:
    if criterion.operator == "must_have" and result.evidence_strength in NO_EVIDENCE:
        if result.outcome != "Fail":
            return "Fail", "fail_no_evidence"
        return "Fail", None
    if criterion.operator == "must_avoid" and result.evidence_strength in NO_EVIDENCE:
        if result.outcome != "Full Pass":
            return "Full Pass", "pass_absent"
        return "Full Pass", None
    return result.outcome, None


def compute_score(
    criteria: Sequence[Criterion],
    results: Mapping[str, CriterionResult],
    role_overlap: RoleOverlapLevel,
    core_requirement: CoreLevel,
    config: ScoringConfig | None = None,
) -> ScoreResult:
    """Turn graded criteria into a 0-100 score with a full, JSON-ready breakdown.

    `results` must contain every criterion key (the evaluate step guarantees this).
    """
    config = config or ScoringConfig()
    missing = [c.key for c in criteria if c.key not in results]
    if missing:
        raise ValueError(f"missing results for criteria: {missing}")

    # 1-3. weights, force rules, percentages, earned
    scored: list[ScoredCriterion] = []
    buckets: list[dict[str, Any]] = []
    forfeited = Decimal(0)
    for operator in OPERATORS:
        in_bucket = [c for c in criteria if c.operator == operator]
        bucket_weight = BUCKET_WEIGHTS[operator]
        if not in_bucket:
            forfeited += bucket_weight
            buckets.append(
                {"bucket": operator, "weight": bucket_weight, "items": 0, "forfeited": True}
            )
            continue
        weights = split_bucket_weight(bucket_weight, [c.importance for c in in_bucket])
        bucket_earned = Decimal(0)
        for criterion, weight in zip(in_bucket, weights, strict=True):
            result = results[criterion.key]
            outcome, forced = _apply_force_rules(criterion, result)
            earned = weight * OUTCOME_PCT[outcome] / _HUNDRED
            bucket_earned += earned
            scored.append(
                ScoredCriterion(
                    key=criterion.key,
                    operator=criterion.operator,
                    importance=criterion.importance,
                    llm_outcome=result.outcome,
                    outcome=outcome,
                    evidence_strength=result.evidence_strength,
                    forced=forced,
                    weight=weight,
                    earned=earned,
                )
            )
        buckets.append(
            {
                "bucket": operator,
                "weight": bucket_weight,
                "items": len(in_bucket),
                "forfeited": False,
                "earned": bucket_earned,
            }
        )

    role_weight = BUCKET_WEIGHTS["role_overlap"]
    core_weight = BUCKET_WEIGHTS["core_requirement"]
    role_earned = role_weight * ROLE_OVERLAP_PCT[role_overlap] / _HUNDRED
    core_earned = core_weight * CORE_PCT[core_requirement] / _HUNDRED
    role_cap = ROLE_OVERLAP_CAP.get(role_overlap)
    core_cap = CORE_CAP.get(core_requirement)
    holistic = [
        {
            "key": "role_overlap",
            "level": role_overlap,
            "weight": role_weight,
            "pct": ROLE_OVERLAP_PCT[role_overlap],
            "earned": role_earned,
            "cap": role_cap,
        },
        {
            "key": "core_requirement",
            "level": core_requirement,
            "weight": core_weight,
            "pct": CORE_PCT[core_requirement],
            "earned": core_earned,
            "cap": core_cap,
        },
    ]

    # 4. forfeit empty buckets and rescale
    earned_total = sum((s.earned for s in scored), Decimal(0)) + role_earned + core_earned
    denominator = _HUNDRED - forfeited
    raw_score = earned_total / denominator * _HUNDRED

    # 5. caps (lowest wins)
    caps: list[dict[str, Any]] = []
    if role_cap is not None:
        caps.append({"source": "role_overlap", "level": role_overlap, "cap": role_cap})
    if core_cap is not None:
        caps.append({"source": "core_requirement", "level": core_requirement, "cap": core_cap})
    cap_values = [c for c in (role_cap, core_cap) if c is not None]
    effective_cap = min(cap_values) if cap_values else None
    after_caps = raw_score if effective_cap is None else min(raw_score, effective_cap)

    # 6. hard-fail penalty (not cumulative)
    hard_fails = [
        s.key
        for s in scored
        if s.operator == "must_have" and s.importance == "high" and s.outcome == "Fail"
    ]
    penalty_applied = config.hard_fail_penalty and bool(hard_fails)
    after_penalty = after_caps - (HARD_FAIL_PENALTY if penalty_applied else Decimal(0))

    # 7. clamp + round
    final = _r2(max(Decimal(0), min(_HUNDRED, after_penalty)))

    breakdown: dict[str, Any] = {
        "engine_version": ENGINE_VERSION,
        "config": {
            "bucket_weights": dict(BUCKET_WEIGHTS),
            "importance_factors": dict(IMPORTANCE_FACTORS),
            "hard_fail_penalty": {"enabled": config.hard_fail_penalty, "points": HARD_FAIL_PENALTY},
        },
        "buckets": buckets,
        "criteria": [
            {
                "key": s.key,
                "operator": s.operator,
                "importance": s.importance,
                "evidence_strength": s.evidence_strength,
                "llm_outcome": s.llm_outcome,
                "outcome": s.outcome,
                "forced": s.forced,
                "weight": s.weight,
                "pct": OUTCOME_PCT[s.outcome],
                "earned": s.earned,
            }
            for s in scored
        ],
        "holistic": holistic,
        "earned_total": earned_total,
        "forfeited_weight": forfeited,
        "denominator": denominator,
        "raw_score": raw_score,
        "caps": {
            "triggered": caps,
            "effective_cap": effective_cap,
            "binding": effective_cap is not None and raw_score > effective_cap,
        },
        "score_after_caps": after_caps,
        "penalty": {
            "applied": penalty_applied,
            "points": HARD_FAIL_PENALTY if penalty_applied else Decimal(0),
            "triggered_by": hard_fails,
        },
        "score_after_penalty": after_penalty,
        "final_score": final,
    }
    return ScoreResult(score=final, criteria=scored, breakdown=to_jsonable(breakdown))


def to_jsonable(value: Any) -> Any:
    """Decimals -> strings (exact), recursively. Keeps breakdown JSONB-safe and lossless."""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f") if value == value.to_integral() else str(value)
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(v) for v in value]
    return value
