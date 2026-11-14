"""Scoring orchestration (PLAN.md §4 run lifecycle, 1.13).

created -> extracting -> parsing_jd -> evaluating -> scoring -> completed
Any step -> failed with error_code. Each transition is committed so it is observable.
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError, ValidationFailedError
from app.core.logging import get_logger
from app.db.models import CriterionEvaluation, Document, Rubric, ScoringRun
from app.llm.client import LLMClient
from app.llm.pricing import quantize_money
from app.pipeline import evaluate as evaluate_step
from app.pipeline.pii import redact
from app.pipeline.pros_cons import derive_pros_cons
from app.pipeline.scoring_math import ENGINE_VERSION, ScoringConfig, compute_score
from app.repositories import documents as documents_repo
from app.repositories import llm_calls as calls_repo
from app.repositories import rubrics as rubrics_repo
from app.repositories import runs as runs_repo
from app.schemas.evaluation import EvaluationOutput
from app.schemas.rubric import Criterion
from app.services.document_service import ingest_pdf, load_text
from app.services.rubric_service import get_or_create_rubric
from app.storage.base import Storage

log = get_logger(__name__)

Steps = Callable[[AsyncSession, ScoringRun, float], Awaitable[None]]


@dataclass(frozen=True)
class PdfInput:
    filename: str
    data: bytes


class ScoringService:
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

    # ------------------------------------------------------------------ public

    async def score_pdfs(
        self, jd: PdfInput, resume: PdfInput, *, model: str | None = None
    ) -> ScoringRun:
        """One-shot: JD PDF + resume PDF -> completed run (or failed run + raised AppError)."""
        model = model or self._settings.llm_default_model

        async def steps(session: AsyncSession, run: ScoringRun, started: float) -> None:
            await self._set_status(session, run, "extracting")
            jd_doc = await ingest_pdf(
                session,
                self._storage,
                self._settings,
                kind="jd",
                filename=jd.filename,
                data=jd.data,
            )
            resume_doc = await ingest_pdf(
                session,
                self._storage,
                self._settings,
                kind="resume",
                filename=resume.filename,
                data=resume.data,
            )
            run.jd_document_id = jd_doc.id
            run.resume_document_id = resume_doc.id
            await self._set_status(session, run, "parsing_jd")
            rubric = await get_or_create_rubric(
                session, self._storage, self._client, jd_doc, model=model
            )
            run.rubric_id = rubric.rubric.id
            await self._evaluate_and_score(session, run, rubric.rubric, resume_doc, started)

        return await self._run(model, steps)

    async def score_documents(
        self, rubric_id: UUID, resume_document_id: UUID, *, model: str | None = None
    ) -> ScoringRun:
        """Score an already-uploaded resume against an existing rubric."""
        model = model or self._settings.llm_default_model

        async def steps(session: AsyncSession, run: ScoringRun, started: float) -> None:
            rubric = await rubrics_repo.get(session, rubric_id)
            resume = await documents_repo.get(session, resume_document_id)
            if rubric is None:
                raise NotFoundError(f"Rubric {rubric_id} not found")
            if resume is None or resume.kind != "resume":
                raise NotFoundError(f"Resume document {resume_document_id} not found")
            run.rubric_id, run.resume_document_id = rubric.id, resume.id
            run.jd_document_id = rubric.jd_document_id
            await self._evaluate_and_score(session, run, rubric, resume, started)

        return await self._run(model, steps)

    async def replay(self, run_id: UUID) -> ScoringRun:
        """Recompute the score from the stored evaluation. No LLM call, no cost."""
        async with self._sessionmaker() as session:
            original = await runs_repo.get(session, run_id)
            if original is None:
                raise NotFoundError(f"Run {run_id} not found")
            if original.evaluation is None or original.rubric_id is None:
                raise ValidationFailedError(
                    "Only runs with a stored evaluation can be replayed",
                    details={"status": original.status},
                )
            rubric = await rubrics_repo.get(session, original.rubric_id)
            if rubric is None:
                raise NotFoundError(f"Rubric {original.rubric_id} not found")
            replay = ScoringRun(
                status="scoring",
                jd_document_id=original.jd_document_id,
                resume_document_id=original.resume_document_id,
                rubric_id=original.rubric_id,
                model=original.model,
                prompt_version=original.prompt_version,
                engine_version=ENGINE_VERSION,
                replay_of_run_id=original.id,
                warnings=list(original.warnings),
            )
            await runs_repo.insert(session, replay)
            started = time.perf_counter()
            evaluation = EvaluationOutput.model_validate(original.evaluation)
            pii_counts = (original.breakdown or {}).get("pii_redactions", {})
            rows = self._apply_score(replay, rubric, evaluation, pii_counts)
            await self._finish(session, replay, rubric, rows, started)
            log.info(
                "run_replayed",
                run_id=str(replay.id),
                replay_of=str(original.id),
                score=str(replay.score),
            )
            return replay

    # ------------------------------------------------------------------ internals

    async def _run(
        self,
        model: str,
        steps: Steps,
    ) -> ScoringRun:
        started = time.perf_counter()
        async with self._sessionmaker() as session:
            run = ScoringRun(
                status="created",
                model=model,
                prompt_version=evaluate_step.PROMPT_VERSION,
                engine_version=ENGINE_VERSION,
                warnings=[],
            )
            await runs_repo.insert(session, run)
            await session.commit()
            run_id = run.id
            log.info("run_created", run_id=str(run_id), model=model)
            try:
                await steps(session, run, started)
                return run
            except AppError as error:
                await self._mark_failed(session, run_id, error.code, error.message)
                error.details.setdefault("run_id", str(run_id))  # lets clients find the run
                raise
            except Exception as error:
                await self._mark_failed(session, run_id, "INTERNAL_ERROR", type(error).__name__)
                raise

    async def _set_status(self, session: AsyncSession, run: ScoringRun, status: str) -> None:
        run.status = status
        await session.commit()
        log.info("run_status", run_id=str(run.id), status=status)

    async def _mark_failed(
        self, session: AsyncSession, run_id: UUID, code: str, message: str
    ) -> None:
        await session.rollback()
        run = await runs_repo.get(session, run_id)
        if run is None:  # pragma: no cover
            return
        run.status = "failed"
        run.error_code = code
        run.error_message = message[:2000]
        run.llm_cost_usd = await calls_repo.sum_cost_for_run(session, run_id)
        await session.commit()
        log.warning("run_failed", run_id=str(run_id), error_code=code)

    async def _evaluate_and_score(
        self,
        session: AsyncSession,
        run: ScoringRun,
        rubric: Rubric,
        resume: Document,
        started: float,
    ) -> None:
        await self._set_status(session, run, "evaluating")
        redaction = redact(await load_text(self._storage, resume))
        criteria = [Criterion.model_validate(c) for c in rubric.criteria]
        result = await evaluate_step.evaluate_resume(
            self._client,
            evaluate_step.RubricView(
                title=rubric.title,
                role_summary=rubric.role_summary,
                core_requirement=rubric.core_requirement,
                criteria=criteria,
            ),
            redaction.text,
            run_id=run.id,
            model=run.model,
        )
        run.warnings = [*run.warnings, *result.warnings]
        run.evaluation = result.evaluation.model_dump()
        await self._set_status(session, run, "scoring")
        rows = self._apply_score(run, rubric, result.evaluation, dict(redaction.counts))
        await self._finish(session, run, rubric, rows, started)

    def _apply_score(
        self,
        run: ScoringRun,
        rubric: Rubric,
        evaluation: EvaluationOutput,
        pii_counts: dict[str, Any],
    ) -> list[CriterionEvaluation]:
        """Compute score, breakdown and pros/cons onto `run`; return the criterion rows."""
        criteria = [Criterion.model_validate(c) for c in rubric.criteria]
        results = {r.key: r for r in evaluation.criteria}
        scored = compute_score(
            criteria,
            results,
            evaluation.role_overlap.level,
            evaluation.core_requirement.level,
            ScoringConfig(hard_fail_penalty=self._settings.scoring_hard_fail_penalty),
        )
        pros_cons = derive_pros_cons(
            scored.criteria,
            {r.key: r.reasoning for r in evaluation.criteria},
            evaluation.role_overlap,
            evaluation.core_requirement,
        )
        run.score = scored.score
        run.engine_version = scored.engine_version
        run.breakdown = {**scored.breakdown, "pii_redactions": pii_counts}
        run.pros, run.cons = pros_cons.as_json()
        run.role_overlap = evaluation.role_overlap.summary
        run.core_demonstration = evaluation.core_requirement.summary
        run.evaluation = evaluation.model_dump()
        return [
            CriterionEvaluation(
                run_id=run.id,
                criterion_key=s.key,
                operator=s.operator,
                importance=s.importance,
                outcome=s.outcome,
                llm_outcome=s.llm_outcome,
                evidence_strength=s.evidence_strength,
                candidate_value=results[s.key].candidate_value,
                reasoning=results[s.key].reasoning,
                weight=s.weight,
                earned=s.earned.quantize(Decimal("0.01")),
                was_forced_fail=s.was_forced_fail,
            )
            for s in scored.criteria
        ]

    async def _finish(
        self,
        session: AsyncSession,
        run: ScoringRun,
        rubric: Rubric,
        rows: list[CriterionEvaluation],
        started: float,
    ) -> None:
        await runs_repo.replace_criterion_evaluations(session, run.id, rows)
        run.llm_cost_usd = await calls_repo.sum_cost_for_run(session, run.id)
        rubric_cost = await calls_repo.sum_cost_for_rubric(session, rubric.id)
        runs_on_rubric = max(1, await rubrics_repo.count_runs(session, rubric.id))
        run.rubric_cost_share_usd = quantize_money(rubric_cost / runs_on_rubric)
        run.latency_ms = int((time.perf_counter() - started) * 1000)
        run.status = "completed"
        await session.commit()
        log.info(
            "run_completed",
            run_id=str(run.id),
            score=str(run.score),
            cost_usd=str(run.llm_cost_usd),
            latency_ms=run.latency_ms,
        )
