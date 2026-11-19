"""Jobs in a user's workspace and the candidates added to them.

Creating a job or adding a candidate only writes rows (status pending / queued); the
background worker (app/services/worker.py) parses the JD and scores each candidate.
"""

import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.logging import get_logger
from app.db.models import Candidate, Document, Job, JobCandidate, Rubric, ScoringRun, User
from app.pipeline import jd_parse
from app.repositories import rubrics as rubrics_repo
from app.schemas.workspace import (
    JobCandidateDetail,
    JobCandidateItem,
    JobCounts,
    JobDetail,
    JobRequirement,
    JobSummary,
)
from app.services.candidate_service import brief
from app.services.document_service import ingest_pdf, ingest_text, load_text
from app.services.run_view import display_verdict, run_detail, whole_score
from app.services.scoring_service import PdfInput
from app.storage.base import Storage

log = get_logger(__name__)

IN_PROGRESS = ("queued", "scoring")
_TITLE_MAX = 120


# Job-board page text that precedes the real title when a JD is copied from a portal.
_PORTAL_NOISE = re.compile(
    r"\b(apply|applicants?|posted|promoted|salary|save|share|easy apply)\b|[$€£₹]", re.I
)
_TITLE_CUT = re.compile(r"\s+(?:at|@|-|\u2013|\u2014|\|)\s+|\s*[(.,;:]")  # en/em dash


def provisional_title(text: str, filename: str, *, pasted: bool) -> str:
    """Shown until the JD is parsed (then the rubric's title replaces it): the first line
    that isn't portal noise, cut at " at <company>" / "(" for run-on one-paragraph JDs."""
    if not pasted:
        return filename.rsplit(".", 1)[0][:_TITLE_MAX] or "Untitled job"
    for raw in text.split("\n"):
        line = raw.strip()
        if not line or _PORTAL_NOISE.search(line):
            continue
        if len(line) > 80:
            line = _TITLE_CUT.split(line, maxsplit=1)[0]
        return (line[:80].rstrip() + ("…" if len(line) > 80 else "")) or "Untitled job"
    return "Untitled job"


def _initial_title(document: Document, text: str) -> str:
    return provisional_title(
        text, document.original_filename, pasted=document.extractor == "pasted_text"
    )


def _source(document: Document) -> str:
    return "text" if document.extractor == "pasted_text" else "pdf"


# ---------------------------------------------------------------- jobs


async def create_job(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    owner: User,
    jd: PdfInput | str,
) -> Job:
    """Store the JD and add a job card for it. Adding the same JD again returns that job."""
    if isinstance(jd, str):
        document = await ingest_text(session, storage, kind="jd", text=jd)
    else:
        document = await ingest_pdf(
            session, storage, settings, kind="jd", filename=jd.filename, data=jd.data
        )
    # Already parsed by anyone with the same model + prompt: the card is ready at once.
    rubric = await rubrics_repo.latest_for_jd(
        session, document.id, jd_parse.PROMPT_VERSION, settings.llm_default_model
    )
    ready = rubric is not None and bool(rubric.criteria)
    stmt = (
        insert(Job)
        .values(
            owner_id=owner.id,
            jd_document_id=document.id,
            title=rubric.title
            if ready and rubric
            else _initial_title(document, await load_text(storage, document)),
            status="ready" if ready else "pending",
            rubric_id=rubric.id if ready and rubric else None,
        )
        .on_conflict_do_nothing(constraint="uq_jobs_owner_id_jd_document_id")
    )
    await session.execute(stmt)
    job = (
        await session.execute(
            select(Job).where(Job.owner_id == owner.id, Job.jd_document_id == document.id)
        )
    ).scalar_one()
    await session.commit()
    log.info("job_created", job_id=str(job.id), status=job.status)
    return job


async def get_owned_job(session: AsyncSession, owner: User, job_id: UUID) -> Job:
    job = await session.get(Job, job_id)
    if job is None or job.owner_id != owner.id:
        raise NotFoundError("Job not found")
    return job


def _counts_columns() -> list[Any]:
    jc = JobCandidate
    verdict = ScoringRun.breakdown["verdict"].astext
    return [
        func.count(jc.id).label("total"),
        func.count(jc.id).filter(jc.status == "scored").label("scored"),
        func.count(jc.id).filter(jc.status.in_(IN_PROGRESS)).label("in_progress"),
        func.count(jc.id).filter(jc.status == "failed").label("failed"),
        func.count(jc.id).filter(jc.status == "scored", verdict == "Strong fit").label("strong"),
        func.max(case((jc.status == "scored", ScoringRun.score))).label("best"),
    ]


def _jobs_query(owner: User) -> Select[Any]:
    return (
        select(Job, Document, *_counts_columns())
        .join(Document, Document.id == Job.jd_document_id)
        .outerjoin(JobCandidate, JobCandidate.job_id == Job.id)
        .outerjoin(ScoringRun, ScoringRun.id == JobCandidate.run_id)
        .where(Job.owner_id == owner.id)
        .group_by(Job.id, Document.id)
    )


def _summary(row: Any) -> JobSummary:
    job, document = row[0], row[1]
    return JobSummary(
        id=job.id,
        title=job.title,
        status=job.status,
        source=_source(document),
        filename=document.original_filename,
        counts=JobCounts(
            total=row.total,
            scored=row.scored,
            in_progress=row.in_progress,
            failed=row.failed,
            strong=row.strong,
        ),
        best_score=whole_score(row.best),
        created_at=job.created_at,
    )


async def list_jobs(session: AsyncSession, owner: User) -> list[JobSummary]:
    stmt = _jobs_query(owner).order_by(Job.created_at.desc())
    return [_summary(row) for row in (await session.execute(stmt)).all()]


async def job_detail(
    session: AsyncSession, storage: Storage, owner: User, job_id: UUID
) -> JobDetail:
    row = (await session.execute(_jobs_query(owner).where(Job.id == job_id))).one_or_none()
    if row is None:
        raise NotFoundError("Job not found")
    job, document = row[0], row[1]
    rubric: Rubric | None = await session.get(Rubric, job.rubric_id) if job.rubric_id else None
    return JobDetail(
        **_summary(row).model_dump(),
        error_code=job.error_code,
        error_message=job.error_message,
        role_summary=rubric.role_summary if rubric else None,
        core_requirement=rubric.core_requirement if rubric else None,
        requirements=[
            JobRequirement(
                key=c["key"],
                name=c["name"],
                attribute=c["attribute"],
                operator=c["operator"],
                importance=c["importance"],
                knockout=c.get("knockout", False),
                verify_in_screening=c.get("verify_in_screening", False),
                values=c.get("values", []),
            )
            for c in (rubric.criteria if rubric else [])
        ],
        jd_text=await load_text(storage, document),
    )


async def job_document(
    session: AsyncSession, storage: Storage, owner: User, job_id: UUID
) -> tuple[Document, bytes]:
    job = await get_owned_job(session, owner, job_id)
    document = await session.get(Document, job.jd_document_id)
    if document is None:  # pragma: no cover - FK
        raise NotFoundError("Job description not found")
    return document, await storage.get(document.storage_key)


async def retry_job(session: AsyncSession, owner: User, job_id: UUID) -> Job:
    job = await get_owned_job(session, owner, job_id)
    if job.status != "failed":
        raise ValidationFailedError("Only a job that failed to read can be retried")
    job.status, job.error_code, job.error_message, job.claimed_at = "pending", None, None, None
    job.parse_queued_at, job.parse_started_at, job.parse_finished_at = func.now(), None, None
    await session.commit()
    await session.refresh(job)
    return job


async def delete_job(session: AsyncSession, owner: User, job_id: UUID) -> None:
    """Removes the card and its shortlist; candidates stay in the database."""
    job = await get_owned_job(session, owner, job_id)
    await session.delete(job)
    await session.commit()
    log.info("job_deleted", job_id=str(job_id))


# ---------------------------------------------------------------- job candidates


def _job_candidates_query() -> Select[JobCandidate, Candidate, Document, ScoringRun]:
    return (
        select(JobCandidate, Candidate, Document, ScoringRun)
        .join(Candidate, Candidate.id == JobCandidate.candidate_id)
        .join(Document, Document.id == Candidate.resume_document_id)
        .outerjoin(ScoringRun, ScoringRun.id == JobCandidate.run_id)
    )


def _item(row: Any) -> JobCandidateItem:
    jc, candidate, document, run = row[0], row[1], row[2], row[3]
    scored = jc.status == "scored" and run is not None
    return JobCandidateItem(
        id=jc.id,
        job_id=jc.job_id,
        candidate=brief(candidate, document),
        status=jc.status,
        source=jc.source,
        score=whole_score(run.score) if scored else None,
        verdict=display_verdict((run.breakdown or {}).get("verdict"), run.score)
        if scored
        else None,
        summary=run.role_overlap if scored else None,
        error_code=jc.error_code,
        error_message=jc.error_message,
        run_id=jc.run_id if scored else None,
        created_at=jc.created_at,
    )


def _rank(item: JobCandidateItem) -> tuple[int, Decimal, Any]:
    """Scored best-first, then in progress (oldest first), then failed."""
    group = {"scored": 0, "scoring": 1, "queued": 1, "failed": 2}[item.status]
    score = Decimal(item.score) if item.score is not None else Decimal(0)
    return (group, -score, item.created_at)


async def list_job_candidates(
    session: AsyncSession, owner: User, job_id: UUID
) -> list[JobCandidateItem]:
    await get_owned_job(session, owner, job_id)
    rows = (
        await session.execute(_job_candidates_query().where(JobCandidate.job_id == job_id))
    ).all()
    return sorted((_item(r) for r in rows), key=_rank)


async def _owned_job_candidate(
    session: AsyncSession, owner: User, job_id: UUID, job_candidate_id: UUID
) -> tuple[Job, Any]:
    job = await get_owned_job(session, owner, job_id)
    row = (
        await session.execute(
            _job_candidates_query().where(
                JobCandidate.id == job_candidate_id, JobCandidate.job_id == job.id
            )
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("Candidate not found in this job")
    return job, row


async def job_candidate_detail(
    session: AsyncSession, owner: User, job_id: UUID, job_candidate_id: UUID
) -> JobCandidateDetail:
    job, row = await _owned_job_candidate(session, owner, job_id, job_candidate_id)
    item = _item(row)
    run = await run_detail(session, item.run_id) if item.run_id else None
    return JobCandidateDetail(
        **item.model_dump(), job_title=job.title, resume_text=row[1].search_text, run=run
    )


async def add_candidates(
    session: AsyncSession,
    owner: User,
    job_id: UUID,
    candidate_ids: list[UUID],
    *,
    source: str,
) -> list[JobCandidateItem]:
    """Queue these (owned) candidates for scoring against the job. Already-added ones are
    returned as they are, not re-scored."""
    job = await get_owned_job(session, owner, job_id)
    owned = set(
        (
            await session.execute(
                select(Candidate.id).where(
                    Candidate.owner_id == owner.id, Candidate.id.in_(candidate_ids)
                )
            )
        ).scalars()
    )
    missing = [str(c) for c in candidate_ids if c not in owned]
    if missing:
        raise NotFoundError("Some candidates were not found", details={"candidate_ids": missing})
    if owned:
        await session.execute(
            insert(JobCandidate)
            .values(
                [
                    {"job_id": job.id, "candidate_id": cid, "status": "queued", "source": source}
                    for cid in dict.fromkeys(candidate_ids)
                ]
            )
            .on_conflict_do_nothing(constraint="uq_job_candidates_job_id_candidate_id")
        )
    await session.commit()
    rows = (
        await session.execute(
            _job_candidates_query().where(
                JobCandidate.job_id == job.id, JobCandidate.candidate_id.in_(candidate_ids)
            )
        )
    ).all()
    log.info("candidates_queued", job_id=str(job.id), count=len(rows), source=source)
    return sorted((_item(r) for r in rows), key=_rank)


async def retry_job_candidate(
    session: AsyncSession, owner: User, job_id: UUID, job_candidate_id: UUID
) -> None:
    _, row = await _owned_job_candidate(session, owner, job_id, job_candidate_id)
    jc: JobCandidate = row[0]
    if jc.status != "failed":
        raise ValidationFailedError("Only a candidate whose scoring failed can be retried")
    await session.execute(
        update(JobCandidate)
        .where(JobCandidate.id == jc.id)
        .values(
            status="queued",
            error_code=None,
            error_message=None,
            claimed_at=None,
            queued_at=func.now(),
            started_at=None,
            finished_at=None,
        )
    )
    await session.commit()


async def remove_job_candidate(
    session: AsyncSession, owner: User, job_id: UUID, job_candidate_id: UUID
) -> None:
    _, row = await _owned_job_candidate(session, owner, job_id, job_candidate_id)
    await session.delete(row[0])
    await session.commit()


async def run_visible_to(session: AsyncSession, owner: User, run_id: UUID) -> bool:
    """A run is visible only through one of the owner's jobs."""
    stmt = (
        select(func.count())
        .select_from(JobCandidate)
        .join(Job, Job.id == JobCandidate.job_id)
        .where(JobCandidate.run_id == run_id, Job.owner_id == owner.id)
    )
    return bool((await session.execute(stmt)).scalar_one())
