"""Jobs and the candidates added to them (HTTP only: parse, delegate, shape)."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.uploads import inline_file, read_pdf, read_resumes
from app.core.config import Settings, get_settings
from app.core.errors import ValidationFailedError
from app.db.models import User
from app.db.session import get_session
from app.schemas.workspace import (
    AddCandidatesResult,
    AddExistingRequest,
    JobCandidateDetail,
    JobCandidateItem,
    JobDetail,
    JobSummary,
)
from app.services import candidate_service, job_service
from app.services.scoring_service import PdfInput
from app.services.worker import get_worker
from app.storage import get_storage

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobSummary])
async def list_jobs(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[JobSummary]:
    return await job_service.list_jobs(session, user)


@router.post("", response_model=JobDetail, status_code=201)
async def create_job(
    jd: UploadFile | None = File(default=None, description="Job description PDF"),
    jd_text: str | None = Form(default=None, description="Job description as pasted text"),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> JobDetail:
    """Add a job from a PDF or pasted text. The same JD twice returns the existing job."""
    jd_input: PdfInput | str
    if jd is not None and not (jd_text and jd_text.strip()):
        jd_input = await read_pdf(jd, settings)
    elif jd is None and jd_text and jd_text.strip():
        jd_input = jd_text
    else:
        raise ValidationFailedError(
            "Send the job description as either a PDF (jd) or text (jd_text), not both"
        )
    storage = get_storage()
    job = await job_service.create_job(session, storage, settings, user, jd_input)
    get_worker().wake()
    return await job_service.job_detail(session, storage, user, job.id)


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> JobDetail:
    return await job_service.job_detail(session, get_storage(), user, job_id)


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> None:
    await job_service.delete_job(session, user, job_id)


@router.post("/{job_id}/retry", response_model=JobDetail)
async def retry_job(
    job_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> JobDetail:
    await job_service.retry_job(session, user, job_id)
    get_worker().wake()
    return await job_service.job_detail(session, get_storage(), user, job_id)


@router.get("/{job_id}/document", response_class=Response)
async def job_document(
    job_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> Response:
    """The original JD (PDF, or the pasted text) for the in-page preview."""
    document, data = await job_service.job_document(session, get_storage(), user, job_id)
    return inline_file(document, data)


@router.get("/{job_id}/candidates", response_model=list[JobCandidateItem])
async def list_job_candidates(
    job_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[JobCandidateItem]:
    """Scored best-first, then in progress, then failed."""
    return await job_service.list_job_candidates(session, user, job_id)


@router.post("/{job_id}/candidates", response_model=AddCandidatesResult, status_code=201)
async def upload_job_candidates(
    job_id: UUID,
    resumes: list[UploadFile] = File(description="One or more resume PDFs"),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AddCandidatesResult:
    """Upload resumes: each joins your database and is queued for scoring on this job."""
    await job_service.get_owned_job(session, user, job_id)
    files, errors = await read_resumes(resumes, settings)
    added, upload_errors = await candidate_service.add_resumes(
        session, get_storage(), settings, user, files
    )
    items = []
    if added:
        items = await job_service.add_candidates(
            session, user, job_id, [c.id for c, _ in added], source="upload"
        )
        get_worker().wake()
    return AddCandidatesResult(added=items, errors=errors + upload_errors)


@router.post("/{job_id}/candidates/existing", response_model=list[JobCandidateItem])
async def add_existing_candidates(
    job_id: UUID,
    body: AddExistingRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[JobCandidateItem]:
    """Add candidates from your database (e.g. search results) and queue them for scoring."""
    items = await job_service.add_candidates(
        session, user, job_id, body.candidate_ids, source="search"
    )
    get_worker().wake()
    return items


@router.get("/{job_id}/candidates/{job_candidate_id}", response_model=JobCandidateDetail)
async def get_job_candidate(
    job_id: UUID,
    job_candidate_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> JobCandidateDetail:
    return await job_service.job_candidate_detail(session, user, job_id, job_candidate_id)


@router.post("/{job_id}/candidates/{job_candidate_id}/retry", status_code=204)
async def retry_job_candidate(
    job_id: UUID,
    job_candidate_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await job_service.retry_job_candidate(session, user, job_id, job_candidate_id)
    get_worker().wake()


@router.delete("/{job_id}/candidates/{job_candidate_id}", status_code=204)
async def remove_job_candidate(
    job_id: UUID,
    job_candidate_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Take the candidate off this job; they stay in your database."""
    await job_service.remove_job_candidate(session, user, job_id, job_candidate_id)
