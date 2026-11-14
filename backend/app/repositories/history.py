"""SQL for the scoring history: completed, non-replay runs grouped by JD."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models import Document, Rubric, ScoringRun


def _in_history() -> ColumnElement[bool]:
    """Runs that belong in history: finished scoring, not a replay of another run."""
    return and_(ScoringRun.status == "completed", ScoringRun.replay_of_run_id.is_(None))


@dataclass(frozen=True)
class JdSummary:
    jd_document_id: UUID
    title: str
    source: str  # "pdf" | "text"
    filename: str
    run_count: int
    best_score: Decimal | None
    last_scored_at: datetime


@dataclass(frozen=True)
class RunSummary:
    id: UUID
    jd_document_id: UUID
    resume_filename: str
    score: Decimal | None
    verdict: str | None
    created_at: datetime


async def list_jds(session: AsyncSession, *, limit: int, offset: int) -> list[JdSummary]:
    runs = select(ScoringRun).where(_in_history()).subquery()
    latest_title = (
        select(Rubric.title)
        .where(Rubric.jd_document_id == Document.id)
        .order_by(Rubric.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    stmt = (
        select(
            Document.id,
            latest_title.label("title"),
            Document.extractor,
            Document.original_filename,
            func.count(runs.c.id).label("run_count"),
            func.max(runs.c.score).label("best_score"),
            func.max(runs.c.created_at).label("last_scored_at"),
        )
        .join(runs, runs.c.jd_document_id == Document.id)
        .where(Document.kind == "jd")
        .group_by(Document.id)
        .order_by(func.max(runs.c.created_at).desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).all()
    return [
        JdSummary(
            jd_document_id=r.id,
            title=r.title or r.original_filename,
            source="text" if r.extractor == "pasted_text" else "pdf",
            filename=r.original_filename,
            run_count=r.run_count,
            best_score=r.best_score,
            last_scored_at=r.last_scored_at,
        )
        for r in rows
    ]


async def list_runs(
    session: AsyncSession, *, jd_document_id: UUID | None, limit: int, offset: int
) -> list[RunSummary]:
    resume = aliased(Document)
    stmt = (
        select(
            ScoringRun.id,
            ScoringRun.jd_document_id,
            resume.original_filename,
            ScoringRun.score,
            ScoringRun.breakdown["verdict"].astext.label("verdict"),
            ScoringRun.created_at,
        )
        .join(resume, resume.id == ScoringRun.resume_document_id)
        .where(_in_history())
        .order_by(ScoringRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if jd_document_id is not None:
        stmt = stmt.where(ScoringRun.jd_document_id == jd_document_id)
    rows = (await session.execute(stmt)).all()
    return [
        RunSummary(
            id=r.id,
            jd_document_id=r.jd_document_id,
            resume_filename=r.original_filename,
            score=r.score,
            verdict=r.verdict,
            created_at=r.created_at,
        )
        for r in rows
    ]
