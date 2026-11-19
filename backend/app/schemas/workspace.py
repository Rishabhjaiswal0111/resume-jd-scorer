"""API shapes for jobs, candidates and search (user-facing: no cost or model)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.runs import RunDetail


class JobRequirement(BaseModel):
    key: str
    name: str
    attribute: str
    operator: str  # must_have | preferred | nice_to_have | must_avoid | may_avoid
    importance: str
    knockout: bool
    verify_in_screening: bool
    values: list[str]


class JobCounts(BaseModel):
    total: int
    scored: int
    in_progress: int
    failed: int
    strong: int


class JobSummary(BaseModel):
    id: UUID
    title: str
    status: str  # pending | parsing | ready | failed
    source: str  # pdf | text
    filename: str
    counts: JobCounts
    best_score: str | None
    created_at: datetime


class JobDetail(JobSummary):
    error_code: str | None
    error_message: str | None
    role_summary: str | None
    core_requirement: str | None
    requirements: list[JobRequirement]
    jd_text: str


class CandidateBrief(BaseModel):
    id: UUID
    name: str
    headline: str | None
    filename: str
    created_at: datetime


class JobCandidateItem(BaseModel):
    id: UUID
    job_id: UUID
    candidate: CandidateBrief
    status: str  # queued | scoring | scored | failed
    source: str  # upload | search
    score: str | None
    verdict: str | None
    summary: str | None
    error_code: str | None
    error_message: str | None
    run_id: UUID | None
    created_at: datetime


class JobCandidateDetail(JobCandidateItem):
    job_title: str
    resume_text: str  # extracted text, for the text view of the resume preview
    run: RunDetail | None


class UploadError(BaseModel):
    filename: str
    code: str
    message: str


class AddCandidatesResult(BaseModel):
    """Per-file outcome of an upload: a bad PDF doesn't fail the whole batch."""

    added: list[JobCandidateItem]
    errors: list[UploadError]


class CandidateUploadResult(BaseModel):
    added: list[CandidateBrief]
    errors: list[UploadError]


class AddExistingRequest(BaseModel):
    candidate_ids: list[UUID] = Field(min_length=1, max_length=100)


class CandidateJobRef(BaseModel):
    job_id: UUID
    job_title: str
    job_candidate_id: UUID
    status: str
    score: str | None


class SearchTerm(BaseModel):
    term: str  # as typed in the query
    matched: bool


class SearchHit(BaseModel):
    candidate: CandidateBrief
    match: int  # 0-100: weighted share of the query terms found in the resume
    terms: list[SearchTerm]
    # Resume excerpt; \u0001 ... \u0002 wrap the matched words (rendered as <mark>).
    snippet: str
    jobs: list[CandidateJobRef]


class SearchResult(BaseModel):
    query: str
    total_candidates: int  # in the database, not just the hits
    terms: list[str]  # the query terms actually searched for
    hits: list[SearchHit]
