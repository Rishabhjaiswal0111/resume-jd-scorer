"""The candidate database: list, search, upload, resume preview."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.uploads import inline_file, read_resumes
from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_session
from app.schemas.workspace import CandidateBrief, CandidateUploadResult, SearchResult
from app.services import candidate_service, search_service
from app.services.candidate_service import brief
from app.storage import get_storage

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("", response_model=list[CandidateBrief])
async def list_candidates(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CandidateBrief]:
    """Everyone in your database, newest first."""
    return await candidate_service.list_candidates(session, user, limit=limit, offset=offset)


@router.get("/search", response_model=SearchResult)
async def search_candidates(
    q: str = Query(min_length=1, max_length=search_service.MAX_QUERY_CHARS),
    limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> SearchResult:
    """Rank your resumes by keywords or any pasted text (e.g. a whole JD)."""
    return await search_service.search(session, user, q, limit=limit)


@router.post("", response_model=CandidateUploadResult, status_code=201)
async def upload_candidates(
    resumes: list[UploadFile] = File(description="One or more resume PDFs"),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> CandidateUploadResult:
    """Add resumes to your database without scoring them against a job."""
    files, errors = await read_resumes(resumes, settings)
    added, upload_errors = await candidate_service.add_resumes(
        session, get_storage(), settings, user, files
    )
    return CandidateUploadResult(
        added=[brief(c, d) for c, d in added], errors=errors + upload_errors
    )


@router.get("/{candidate_id}/resume", response_class=Response)
async def candidate_resume(
    candidate_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """The resume PDF, for the in-page preview."""
    _, document = await candidate_service.get_owned(session, user, candidate_id)
    return inline_file(document, await get_storage().get(document.storage_key))
