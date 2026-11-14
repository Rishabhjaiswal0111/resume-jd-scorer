"""History views: past completed runs grouped by JD (user-facing: no cost or model)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import history as history_repo
from app.schemas.runs import JdHistoryItem, RunHistoryItem
from app.services.run_view import display_verdict, whole_score


async def list_jds(session: AsyncSession, *, limit: int, offset: int) -> list[JdHistoryItem]:
    rows = await history_repo.list_jds(session, limit=limit, offset=offset)
    return [
        JdHistoryItem(
            jd_document_id=r.jd_document_id,
            title=r.title,
            source=r.source,
            filename=r.filename,
            run_count=r.run_count,
            best_score=whole_score(r.best_score),
            last_scored_at=r.last_scored_at,
        )
        for r in rows
    ]


async def list_runs(
    session: AsyncSession, *, jd_document_id: UUID | None, limit: int, offset: int
) -> list[RunHistoryItem]:
    rows = await history_repo.list_runs(
        session, jd_document_id=jd_document_id, limit=limit, offset=offset
    )
    return [
        RunHistoryItem(
            id=r.id,
            jd_document_id=r.jd_document_id,
            resume_filename=r.resume_filename,
            score=whole_score(r.score),
            verdict=display_verdict(r.verdict, r.score),
            created_at=r.created_at,
        )
        for r in rows
    ]
