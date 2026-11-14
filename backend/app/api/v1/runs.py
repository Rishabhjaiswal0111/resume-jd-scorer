"""Scoring endpoints (HTTP only: parse, delegate, shape)."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import PdfTooLargeError
from app.db.session import get_session, get_sessionmaker
from app.llm.client import LLMClient
from app.schemas.runs import RunDetail
from app.services.run_view import run_detail
from app.services.scoring_service import PdfInput, ScoringService
from app.storage import get_storage

router = APIRouter(tags=["runs"])


def get_scoring_service() -> ScoringService:
    """Overridable in tests via app.dependency_overrides."""
    settings = get_settings()
    sessionmaker, storage = get_sessionmaker(), get_storage()
    return ScoringService(
        settings, sessionmaker, storage, LLMClient(settings, sessionmaker, storage)
    )


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
    jd: UploadFile = File(description="Job description PDF"),
    resume: UploadFile = File(description="Resume PDF"),
    model: str | None = Form(default=None),
    service: ScoringService = Depends(get_scoring_service),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RunDetail:
    """One-shot: upload a JD and a resume, get the completed run back."""
    run = await service.score_pdfs(
        await _read_pdf(jd, settings), await _read_pdf(resume, settings), model=model
    )
    return await run_detail(session, run.id)


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: UUID, session: AsyncSession = Depends(get_session)) -> RunDetail:
    return await run_detail(session, run_id)
