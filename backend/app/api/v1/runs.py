"""Scoring endpoints (HTTP only: parse, delegate, shape)."""

from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import PdfTooLargeError, ValidationFailedError
from app.db.session import get_session, get_sessionmaker
from app.llm.client import LLMClient
from app.schemas.runs import JdHistoryItem, RunDetail, RunHistoryItem
from app.services import history_service
from app.services.run_view import run_detail
from app.services.scoring_service import PdfInput, ScoringService
from app.storage import get_storage

router = APIRouter(tags=["runs"])


@lru_cache
def get_llm_client() -> LLMClient:
    """One LLM client per process, so its HTTP connection pool is reused across requests.
    Closed in the app lifespan."""
    settings = get_settings()
    return LLMClient(settings, get_sessionmaker(), get_storage())


def get_scoring_service() -> ScoringService:
    """Overridable in tests via app.dependency_overrides."""
    settings = get_settings()
    return ScoringService(settings, get_sessionmaker(), get_storage(), get_llm_client())


async def _read_pdf(upload: UploadFile, settings: Settings) -> PdfInput:
    # Read one byte past the limit so oversized files are rejected without buffering them all.
    data = await upload.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise PdfTooLargeError(
            f"{upload.filename} is larger than {settings.max_upload_bytes} bytes",
            details={"max_bytes": settings.max_upload_bytes},
        )
    return PdfInput(upload.filename or "upload.pdf", data)


@router.post("/score", response_model=RunDetail)
async def score(
    resume: UploadFile = File(description="Resume PDF"),
    jd: UploadFile | None = File(default=None, description="Job description PDF"),
    jd_text: str | None = Form(default=None, description="Job description as pasted text"),
    model: str | None = Form(default=None),
    service: ScoringService = Depends(get_scoring_service),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RunDetail:
    """One-shot: a JD (PDF or pasted text) and a resume PDF -> the completed run."""
    jd_input: PdfInput | str
    if jd is not None and not (jd_text and jd_text.strip()):
        jd_input = await _read_pdf(jd, settings)
    elif jd is None and jd_text and jd_text.strip():
        jd_input = jd_text
    else:
        raise ValidationFailedError(
            "Send the job description as either a PDF (jd) or text (jd_text), not both"
        )
    run = await service.score_pdfs(jd_input, await _read_pdf(resume, settings), model=model)
    return await run_detail(session, run.id)


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: UUID, session: AsyncSession = Depends(get_session)) -> RunDetail:
    return await run_detail(session, run_id)


@router.get("/jds", response_model=list[JdHistoryItem])
async def list_jds(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[JdHistoryItem]:
    """JDs that have completed runs, most recently scored first."""
    return await history_service.list_jds(session, limit=limit, offset=offset)


@router.get("/runs", response_model=list[RunHistoryItem])
async def list_runs(
    jd_document_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[RunHistoryItem]:
    """Completed runs, newest first; filter by JD with jd_document_id."""
    return await history_service.list_runs(
        session, jd_document_id=jd_document_id, limit=limit, offset=offset
    )
