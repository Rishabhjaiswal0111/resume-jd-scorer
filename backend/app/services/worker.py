"""Background JD parsing and scoring, with Postgres as the queue.

Work is rows, not messages: a job with status `pending` needs its JD parsed, and a
job_candidate with status `queued` (on a `ready` job) needs scoring. Each worker coroutine
claims one row at a time with `FOR UPDATE SKIP LOCKED`, so several workers (or several API
processes) never take the same row, and nothing is lost on restart: unfinished rows are
still in the table. A claim older than `worker_stale_claim_seconds` (a crash mid-run) is
handed out again.

The API wakes the workers after inserting work; they also poll, so rows written by other
processes (e.g. `make demo`) are picked up. Moving to Redis/Arq later (PLAN 5.1) replaces
only the claim/wake mechanics.

No DB transaction is held during an LLM call (ADR-0007): claims commit before the work,
and the scoring service commits before each LLM step.
"""

import asyncio
import contextlib
import time
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.errors import AppError, LLMResponsePendingError
from app.core.logging import get_logger
from app.core.timing import elapsed_ms
from app.db.models import Candidate, Document, Job, JobCandidate
from app.db.session import get_sessionmaker
from app.llm.client import LLMClient
from app.services.rubric_service import get_or_create_rubric
from app.services.scoring_service import ScoringService
from app.storage import get_storage
from app.storage.base import Storage

log = get_logger(__name__)

_PENDING_MESSAGE = "Timed out waiting for the model's answer. Retry to try again."


class Worker:
    def __init__(
        self,
        settings: Settings,
        sessionmaker: async_sessionmaker[AsyncSession],
        storage: Storage,
        client: LLMClient,
    ) -> None:
        self._settings = settings
        self._sessionmaker = sessionmaker
        self._storage = storage
        self._client = client
        self._scoring = ScoringService(settings, sessionmaker, storage, client)
        self._wake = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        if self._tasks:
            return
        self._tasks = [
            asyncio.create_task(self._loop(i), name=f"worker-{i}")
            for i in range(self._settings.worker_concurrency)
        ]
        log.info("workers_started", count=len(self._tasks))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    @property
    def client(self) -> LLMClient:
        return self._client

    def wake(self) -> None:
        """New work was written: stop waiting for the next poll."""
        self._wake.set()

    async def _loop(self, index: int) -> None:
        while True:
            try:
                worked = await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # never let one bad row kill the worker
                log.exception("worker_iteration_failed", worker=index)
                worked = False
            if worked:
                continue
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), self._settings.worker_poll_seconds)
            self._wake.clear()

    # ------------------------------------------------------------------ one unit of work

    async def run_once(self) -> bool:
        """Claim and process one job parse or one candidate score. False if there was none."""
        job_id = await self._claim_job()
        if job_id is not None:
            try:
                await self._parse_job(job_id)
            except asyncio.CancelledError:
                await self._release(Job, job_id, "pending")
                raise
            return True
        job_candidate_id = await self._claim_job_candidate()
        if job_candidate_id is not None:
            try:
                await self._score(job_candidate_id)
            except asyncio.CancelledError:
                await self._release(JobCandidate, job_candidate_id, "queued")
                raise
            return True
        return False

    async def _release(self, model: type[Job] | type[JobCandidate], row_id: UUID, to: str) -> None:
        """Shutdown (deploy, dev reload) mid-task: hand the row back at once instead of
        leaving it claimed until the stale timeout. Shielded so the cancel can't stop it."""

        started = "parse_started_at" if model is Job else "started_at"

        async def release() -> None:
            async with self._sessionmaker() as session:
                await session.execute(
                    update(model)
                    .where(model.id == row_id)
                    .values({"status": to, "claimed_at": None, started: None})
                )
                await session.commit()

        try:
            await asyncio.shield(release())
            log.info("claim_released", table=model.__tablename__, id=str(row_id))
        except Exception:  # the stale timeout still recovers it
            log.exception("claim_release_failed", id=str(row_id))

    async def run_until_idle(self, max_units: int = 100) -> int:
        """Process everything currently claimable (tests, CLI). Returns units processed."""
        done = 0
        while done < max_units and await self.run_once():
            done += 1
        return done

    def _stale_before(self) -> datetime:
        return datetime.now(UTC) - timedelta(seconds=self._settings.worker_stale_claim_seconds)

    async def _claim_job(self) -> UUID | None:
        async with self._sessionmaker() as session:
            pick = (
                select(Job.id)
                .where(
                    (Job.status == "pending")
                    | ((Job.status == "parsing") & (Job.claimed_at < self._stale_before()))
                )
                .order_by(Job.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
                .scalar_subquery()
            )
            job_id = (
                await session.execute(
                    update(Job)
                    .where(Job.id == pick)
                    .values(
                        status="parsing",
                        claimed_at=func.now(),
                        parse_started_at=func.now(),
                        parse_finished_at=None,
                    )
                    .returning(Job.id)
                )
            ).scalar_one_or_none()
            await session.commit()
            return job_id

    async def _claim_job_candidate(self) -> UUID | None:
        async with self._sessionmaker() as session:
            pick = (
                select(JobCandidate.id)
                .join(Job, Job.id == JobCandidate.job_id)
                .where(
                    Job.status == "ready",
                    (JobCandidate.status == "queued")
                    | (
                        (JobCandidate.status == "scoring")
                        & (JobCandidate.claimed_at < self._stale_before())
                    ),
                )
                .order_by(JobCandidate.created_at)
                .limit(1)
                .with_for_update(of=JobCandidate, skip_locked=True)
                .scalar_subquery()
            )
            job_candidate_id = (
                await session.execute(
                    update(JobCandidate)
                    .where(JobCandidate.id == pick)
                    .values(
                        status="scoring",
                        claimed_at=func.now(),
                        started_at=func.now(),
                        finished_at=None,
                        attempts=JobCandidate.attempts + 1,
                    )
                    .returning(JobCandidate.id)
                )
            ).scalar_one_or_none()
            await session.commit()
            return job_candidate_id

    async def _parse_job(self, job_id: UUID) -> None:
        async with self._sessionmaker() as session:
            job = await session.get(Job, job_id)
            document = await session.get(Document, job.jd_document_id) if job else None
            if job is None or document is None:  # deleted after the claim
                return
            log.info("job_parse_started", job_id=str(job_id))
            try:
                result = await get_or_create_rubric(
                    session,
                    self._storage,
                    self._client,
                    document,
                    model=self._settings.llm_default_model,
                )
            except AppError as error:
                await self._finish_job(session, job_id, error)
                return
            values: dict[str, object] = {"status": "ready", "rubric_id": result.rubric.id}
            values["title"] = result.rubric.title
            values["parse_finished_at"] = func.now()
            await session.execute(update(Job).where(Job.id == job_id).values(**values))
            await session.commit()
            log.info("job_ready", job_id=str(job_id), criteria=len(result.rubric.criteria))
        self.wake()  # its queued candidates can be scored now

    async def _finish_job(self, session: AsyncSession, job_id: UUID, error: AppError) -> None:
        await session.rollback()
        message = _PENDING_MESSAGE if isinstance(error, LLMResponsePendingError) else error.message
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status="failed",
                error_code=error.code,
                error_message=message[:2000],
                parse_finished_at=func.now(),
            )
        )
        await session.commit()
        log.warning("job_parse_failed", job_id=str(job_id), error_code=error.code)

    async def _score(self, job_candidate_id: UUID) -> None:
        async with self._sessionmaker() as session:
            row = (
                await session.execute(
                    select(JobCandidate, Job.rubric_id, Candidate.resume_document_id)
                    .join(Job, Job.id == JobCandidate.job_id)
                    .join(Candidate, Candidate.id == JobCandidate.candidate_id)
                    .where(JobCandidate.id == job_candidate_id)
                )
            ).one_or_none()
            await session.commit()  # no transaction held while scoring
        if row is None or row.rubric_id is None:
            return
        log.info("candidate_scoring_started", job_candidate_id=str(job_candidate_id))
        started = time.perf_counter()
        values: dict[str, object]
        try:
            run = await self._scoring.score_documents(row.rubric_id, row.resume_document_id)
            values = {"status": "scored", "run_id": run.id, "error_code": None}
            values["error_message"] = None
        except AppError as error:
            run_id = error.details.get("run_id")
            values = {
                "status": "failed",
                "run_id": UUID(run_id) if run_id else None,
                "error_code": error.code,
                "error_message": (
                    _PENDING_MESSAGE
                    if isinstance(error, LLMResponsePendingError)
                    else error.message
                )[:2000],
            }
        async with self._sessionmaker() as session:
            # Only if still claimed by us (not removed from the job meanwhile).
            await session.execute(
                update(JobCandidate)
                .where(JobCandidate.id == job_candidate_id, JobCandidate.status == "scoring")
                .values(**values, finished_at=func.now())
            )
            await session.commit()
        log.info(
            "candidate_scoring_done",
            job_candidate_id=str(job_candidate_id),
            status=values["status"],
            duration_ms=elapsed_ms(started),
        )


def background_settings(settings: Settings) -> Settings:
    """Manual mode: wait long for each answer instead of failing a run every 20 s."""
    return settings.model_copy(
        update={"manual_llm_wait_seconds": settings.manual_llm_background_wait_seconds}
    )


@lru_cache
def get_worker() -> Worker:
    """One worker pool per process, started in the app lifespan."""
    settings = background_settings(get_settings())
    storage = get_storage()
    client = LLMClient(settings, get_sessionmaker(), storage)
    return Worker(settings, get_sessionmaker(), storage, client)
