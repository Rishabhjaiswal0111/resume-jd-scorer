"""Assemble the API view of a run from its rows (no business logic, just shaping)."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.repositories import llm_calls as calls_repo
from app.repositories import rubrics as rubrics_repo
from app.repositories import runs as runs_repo
from app.schemas.runs import (
    CostView,
    CriterionView,
    GroupAdjustment,
    Holistic,
    Point,
    RunDetail,
    ScreeningQuestion,
)


def money(value: Decimal | None) -> str | None:
    """Plain decimal string without exponent or trailing zeros: 0.00026364, 0."""
    if value is None:
        return None
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


async def run_detail(session: AsyncSession, run_id: UUID) -> RunDetail:
    run = await runs_repo.get(session, run_id)
    if run is None:
        raise NotFoundError(f"Run {run_id} not found")
    rubric = await rubrics_repo.get(session, run.rubric_id) if run.rubric_id else None
    names = {c["key"]: c["name"] for c in rubric.criteria} if rubric else {}
    full_breakdown = run.breakdown or {}
    breakdown = {c["key"]: c for c in full_breakdown.get("criteria", [])}
    rows = await runs_repo.criterion_evaluations(session, run.id)
    calls = await calls_repo.list_for_run(session, run.id)
    reported = [c.provider_reported_cost_usd for c in calls if c.provider_reported_cost_usd]
    evaluation = run.evaluation or {}

    # Rubric order, not insertion order, so the table reads like the JD.
    order = {key: i for i, key in enumerate(names)}
    rows.sort(key=lambda r: order.get(r.criterion_key, len(order)))

    return RunDetail(
        id=run.id,
        status=run.status,
        error_code=run.error_code,
        error_message=run.error_message,
        score=str(run.score) if run.score is not None else None,  # always 2 dp: "55.20"
        verdict=full_breakdown.get("verdict"),  # absent on engine 1.0.0 runs
        role_title=rubric.title if rubric else None,
        model=run.model,
        engine_version=run.engine_version,
        role_overlap=Holistic(**evaluation["role_overlap"]) if evaluation else None,
        core_requirement=Holistic(**evaluation["core_requirement"]) if evaluation else None,
        pros=[Point(**p) for p in run.pros or []],
        cons=[Point(**c) for c in run.cons or []],
        criteria=[
            CriterionView(
                key=r.criterion_key,
                name=names.get(r.criterion_key, r.criterion_key),
                operator=r.operator,
                importance=r.importance,
                outcome=r.outcome,
                llm_outcome=r.llm_outcome,
                evidence_strength=r.evidence_strength,
                candidate_value=r.candidate_value,
                reasoning=r.reasoning,
                weight=money(r.weight) or "0",
                earned=money(r.earned) or "0",
                forced=breakdown.get(r.criterion_key, {}).get("forced"),
                knockout=breakdown.get(r.criterion_key, {}).get("knockout", False),
                group=breakdown.get(r.criterion_key, {}).get("group", ""),
            )
            for r in rows
        ],
        screening=[
            ScreeningQuestion(
                key=r.criterion_key,
                name=names.get(r.criterion_key, r.criterion_key),
                reasoning=r.reasoning,
            )
            for r in rows
            if r.outcome == "Unknown"
        ],
        group_adjustments=[
            GroupAdjustment(**g) for g in full_breakdown.get("group_adjustments", [])
        ],
        warnings=list(run.warnings or []),
        cost=CostView(
            run_llm_cost_usd=money(run.llm_cost_usd),
            rubric_cost_share_usd=money(run.rubric_cost_share_usd),
            provider_reported_usd=money(sum(reported, Decimal(0))) if reported else None,
            llm_calls=len(calls),
        ),
        latency_ms=run.latency_ms,
        created_at=run.created_at,
    )
