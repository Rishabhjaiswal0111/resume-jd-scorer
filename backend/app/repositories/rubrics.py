"""SQL for rubrics."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Rubric, ScoringRun


async def get(session: AsyncSession, rubric_id: UUID) -> Rubric | None:
    return await session.get(Rubric, rubric_id)


async def latest_for_jd(
    session: AsyncSession, jd_document_id: UUID, prompt_version: str, model: str
) -> Rubric | None:
    """Cached rubric for this JD, produced by the same prompt version and model."""
    stmt = (
        select(Rubric)
        .where(
            Rubric.jd_document_id == jd_document_id,
            Rubric.prompt_version == prompt_version,
            Rubric.model == model,
        )
        .order_by(Rubric.version.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def next_version(session: AsyncSession, jd_document_id: UUID) -> int:
    stmt = select(func.coalesce(func.max(Rubric.version), 0)).where(
        Rubric.jd_document_id == jd_document_id
    )
    return int((await session.execute(stmt)).scalar_one()) + 1


async def insert(session: AsyncSession, rubric: Rubric) -> Rubric:
    session.add(rubric)
    await session.flush()
    return rubric


async def count_runs(session: AsyncSession, rubric_id: UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(ScoringRun)
        .where(ScoringRun.rubric_id == rubric_id, ScoringRun.replay_of_run_id.is_(None))
    )
    return int((await session.execute(stmt)).scalar_one())
