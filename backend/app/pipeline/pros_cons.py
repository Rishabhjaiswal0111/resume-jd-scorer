"""Derive pros / cons from graded criteria (PLAN.md §7.5). PURE: no I/O.

- Full Pass reasoning -> pros; Partial Pass / Fail -> cons.
- Holistic summaries -> cons if their level carries a cap, else pros.
- Unknown (verify-in-screening) criteria are neither; they become screening questions.
- Sorted by operator (must_have first), then importance (high first), then rubric order.
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from app.pipeline.scoring_math import CORE_CAP, ROLE_OVERLAP_CAP, ScoredCriterion
from app.schemas.evaluation import CoreRequirementAssessment, RoleOverlap
from app.schemas.rubric import OPERATORS

_OPERATOR_RANK = {op: i for i, op in enumerate(OPERATORS)}
_IMPORTANCE_RANK = {"high": 0, "normal": 1}
# Holistic items sort before criteria: they are the headline of the assessment.
_HOLISTIC_RANK = -1


@dataclass(frozen=True)
class Point:
    text: str
    source: str  # criterion key, "role_overlap" or "core_requirement"
    operator: str | None
    importance: str | None
    outcome: str


@dataclass(frozen=True)
class ProsCons:
    pros: list[Point]
    cons: list[Point]

    def as_json(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return [asdict(p) for p in self.pros], [asdict(c) for c in self.cons]


def derive_pros_cons(
    scored: Sequence[ScoredCriterion],
    reasoning: Mapping[str, str],
    role_overlap: RoleOverlap,
    core_requirement: CoreRequirementAssessment,
) -> ProsCons:
    ranked: list[tuple[tuple[int, int, int], bool, Point]] = []

    holistic = [
        (
            "role_overlap",
            role_overlap.level,
            role_overlap.summary,
            role_overlap.level in ROLE_OVERLAP_CAP,
        ),
        (
            "core_requirement",
            core_requirement.level,
            core_requirement.summary,
            core_requirement.level in CORE_CAP,
        ),
    ]
    for i, (source, level, summary, capped) in enumerate(holistic):
        point = Point(text=summary, source=source, operator=None, importance=None, outcome=level)
        ranked.append(((_HOLISTIC_RANK, 0, i), not capped, point))

    for i, s in enumerate(scored):
        if s.outcome == "Unknown":  # not a pro or a con: it is a screening question
            continue
        point = Point(
            text=reasoning.get(s.key, ""),
            source=s.key,
            operator=s.operator,
            importance=s.importance,
            outcome=s.outcome,
        )
        rank = (_OPERATOR_RANK[s.operator], _IMPORTANCE_RANK[s.importance], i)
        ranked.append((rank, s.outcome == "Full Pass", point))

    ranked.sort(key=lambda item: item[0])
    return ProsCons(
        pros=[p for _, is_pro, p in ranked if is_pro],
        cons=[p for _, is_pro, p in ranked if not is_pro],
    )
