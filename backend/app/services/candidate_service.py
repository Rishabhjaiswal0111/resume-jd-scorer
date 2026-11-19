"""A user's candidate database: resumes uploaded to a job or straight into the database."""

import re
from dataclasses import dataclass
from pathlib import PurePath
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.core.logging import get_logger
from app.db.models import Candidate, Document, User
from app.pipeline.pii import find_name
from app.schemas.workspace import CandidateBrief, UploadError
from app.services.document_service import ingest_pdf, load_text
from app.storage.base import Storage

log = get_logger(__name__)

_CONTACT = re.compile(r"@|https?://|linkedin\.com|\+?\d[\d ()-]{6,}")
_MAX_HEADLINE = 140


@dataclass(frozen=True)
class ResumeFile:
    filename: str
    data: bytes


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.split("\n") if line.strip()]


def _name_and_rest(text: str) -> tuple[str | None, list[str]]:
    """The name and the lines after it. Two-column PDFs can wrap a name over two lines
    ("Name: Amara" / "Petrov"), so the first two lines joined are tried too. Display only:
    PII redaction keeps its stricter one-line rule (ADR-0007)."""
    lines = _lines(text)
    name = find_name(text)
    if name:
        return name, lines[1:]
    if len(lines) >= 2 and len(lines[1].split()) == 1:
        joined = find_name(f"{lines[0]} {lines[1]}")
        if joined:
            return joined, lines[2:]
    return None, lines


def display_name(text: str, filename: str) -> str:
    """The resume's own name line, else the file name without extension."""
    name, _ = _name_and_rest(text)
    if name:
        return name
    stem = PurePath(filename).stem
    return re.sub(r"[_\-]+", " ", stem).strip() or "Unnamed resume"


def headline(text: str) -> str | None:
    """The line after the name ("Senior Backend Engineer · 8 years"), if it is one. A line
    wrapped by the PDF layout ("... 9 years in" / "product management") is rejoined."""
    name, rest = _name_and_rest(text)
    if name is None or not rest:
        return None
    line = rest[0]
    if len(rest) > 1 and rest[1][:1].islower():
        line = f"{line} {rest[1]}"
    if _CONTACT.search(line) or len(line) > _MAX_HEADLINE:
        return None
    return line


def brief(candidate: Candidate, document: Document) -> CandidateBrief:
    return CandidateBrief(
        id=candidate.id,
        name=candidate.name,
        headline=candidate.headline,
        filename=document.original_filename,
        created_at=candidate.created_at,
    )


async def upsert_candidate(
    session: AsyncSession, storage: Storage, owner: User, document: Document
) -> Candidate:
    """The owner's candidate for this resume document, created if new (race-safe)."""
    text = await load_text(storage, document)
    derived = {"name": display_name(text, document.original_filename), "headline": headline(text)}
    stmt = (
        insert(Candidate)
        .values(owner_id=owner.id, resume_document_id=document.id, search_text=text, **derived)
        # Re-uploading refreshes what is derived from the text (e.g. after a parsing fix).
        .on_conflict_do_update(constraint="uq_candidates_owner_id_resume_document_id", set_=derived)
    )
    await session.execute(stmt)
    candidate = (
        await session.execute(
            select(Candidate).where(
                Candidate.owner_id == owner.id, Candidate.resume_document_id == document.id
            )
        )
    ).scalar_one()
    await session.commit()
    return candidate


async def add_resumes(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    owner: User,
    files: list[ResumeFile],
) -> tuple[list[tuple[Candidate, Document]], list[UploadError]]:
    """Ingest each PDF and add it to the owner's database. Bad files are reported, not raised."""
    added: list[tuple[Candidate, Document]] = []
    errors: list[UploadError] = []
    for file in files:
        try:
            document = await ingest_pdf(
                session, storage, settings, kind="resume", filename=file.filename, data=file.data
            )
            added.append((await upsert_candidate(session, storage, owner, document), document))
        except AppError as error:
            # Raised before any write (extraction / size). Commit, never rollback(): a
            # rollback expires the user and earlier rows and crashes the next access
            # (ADR-0007).
            await session.commit()
            errors.append(
                UploadError(filename=file.filename, code=error.code, message=error.message)
            )
    log.info("resumes_added", owner_id=str(owner.id), added=len(added), errors=len(errors))
    return added, errors


async def get_owned(
    session: AsyncSession, owner: User, candidate_id: UUID
) -> tuple[Candidate, Document]:
    stmt = (
        select(Candidate, Document)
        .join(Document, Document.id == Candidate.resume_document_id)
        .where(Candidate.id == candidate_id, Candidate.owner_id == owner.id)
    )
    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        raise NotFoundError("Candidate not found")
    return row[0], row[1]


async def list_candidates(
    session: AsyncSession, owner: User, *, limit: int, offset: int
) -> list[CandidateBrief]:
    stmt = (
        select(Candidate, Document)
        .join(Document, Document.id == Candidate.resume_document_id)
        .where(Candidate.owner_id == owner.id)
        .order_by(Candidate.created_at.desc(), Candidate.name)
        .limit(limit)
        .offset(offset)
    )
    return [brief(c, d) for c, d in (await session.execute(stmt)).all()]
