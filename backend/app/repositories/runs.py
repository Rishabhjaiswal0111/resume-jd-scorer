"""SQL for scoring_runs and criterion_evaluations."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CriterionEvaluation, ScoringRun


async def get(session: AsyncSession, run_id: UUID) -> ScoringRun | None:
    return await session.get(ScoringRun, run_id)


async def insert(session: AsyncSession, run: ScoringRun) -> ScoringRun:
    session.add(run)
    await session.flush()
    return run


async def replace_criterion_evaluations(
    session: AsyncSession, run_id: UUID, rows: list[CriterionEvaluation]
) -> None:
    await session.execute(delete(CriterionEvaluation).where(CriterionEvaluation.run_id == run_id))
    session.add_all(rows)
    await session.flush()


async def criterion_evaluations(session: AsyncSession, run_id: UUID) -> list[CriterionEvaluation]:
    stmt = (
        select(CriterionEvaluation)
        .where(CriterionEvaluation.run_id == run_id)
        .order_by(CriterionEvaluation.created_at, CriterionEvaluation.criterion_key)
    )
    return list((await session.execute(stmt)).scalars())
