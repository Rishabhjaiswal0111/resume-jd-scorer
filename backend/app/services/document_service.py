"""Store an uploaded PDF + its extracted text, deduplicated by (kind, sha256)."""

import asyncio
import hashlib

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import PdfTooLargeError, ValidationFailedError
from app.core.logging import get_logger
from app.db.models import Document
from app.pipeline.extract import extract_pdf, normalize_text
from app.repositories import documents as documents_repo
from app.storage.base import Storage

log = get_logger(__name__)


async def ingest_pdf(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    *,
    kind: str,
    filename: str,
    data: bytes,
) -> Document:
    """Return the stored document for these bytes, extracting + storing it if new.

    Commits on insert so the document survives a later pipeline failure.
    """
    if len(data) > settings.max_upload_bytes:
        raise PdfTooLargeError(
            f"File is {len(data)} bytes; the limit is {settings.max_upload_bytes}",
            details={"size_bytes": len(data), "max_bytes": settings.max_upload_bytes},
        )
    sha256 = hashlib.sha256(data).hexdigest()
    existing = await documents_repo.get_by_hash(session, kind, sha256)
    if existing is not None:
        log.info("document_dedupe_hit", kind=kind, document_id=str(existing.id))
        return existing

    # pdfium / pdfminer are CPU-bound and synchronous.
    extraction = await asyncio.to_thread(extract_pdf, data, max_pages=settings.max_pdf_pages)

    pdf_key = f"documents/{kind}/{sha256}.pdf"
    text_key = f"documents/{kind}/{sha256}.txt"
    await storage.put(pdf_key, data)
    await storage.put(text_key, extraction.text.encode("utf-8"))

    document = Document(
        kind=kind,
        original_filename=filename[:255],
        sha256=sha256,
        size_bytes=len(data),
        storage_key=pdf_key,
        page_count=extraction.page_count,
        extractor=extraction.extractor,
        text_storage_key=text_key,
        char_count=extraction.char_count,
        is_scanned=extraction.is_scanned,
    )
    try:
        # Savepoint, not a full rollback on conflict: rollback() would expire every object
        # in the request's session (the run, the JD document) and crash the next access.
        async with session.begin_nested():
            await documents_repo.insert(session, document)
        await session.commit()
    except IntegrityError:
        # Same file uploaded concurrently: the other insert won; use its row.
        winner = await documents_repo.get_by_hash(session, kind, sha256)
        if winner is None:  # pragma: no cover - would mean the unique constraint lied
            raise
        return winner
    log.info(
        "document_stored",
        kind=kind,
        document_id=str(document.id),
        pages=document.page_count,
        chars=document.char_count,
    )
    return document


# Pasted text: below this it is almost certainly not a whole job description; above it,
# about 20 dense PDF pages, matching the PDF page limit.
MIN_TEXT_CHARS = 200
MAX_TEXT_CHARS = 60_000


async def ingest_text(session: AsyncSession, storage: Storage, *, kind: str, text: str) -> Document:
    """Store pasted text (e.g. a JD copied from a job portal), deduplicated by content."""
    normalized = normalize_text(text)
    if len(normalized) < MIN_TEXT_CHARS:
        raise ValidationFailedError(
            f"Pasted text is too short ({len(normalized)} characters, need {MIN_TEXT_CHARS}+)",
            details={"chars": len(normalized), "min_chars": MIN_TEXT_CHARS},
        )
    if len(normalized) > MAX_TEXT_CHARS:
        raise ValidationFailedError(
            f"Pasted text is too long ({len(normalized)} characters, max {MAX_TEXT_CHARS})",
            details={"chars": len(normalized), "max_chars": MAX_TEXT_CHARS},
        )
    data = normalized.encode("utf-8")
    sha256 = hashlib.sha256(data).hexdigest()
    existing = await documents_repo.get_by_hash(session, kind, sha256)
    if existing is not None:
        return existing

    key = f"documents/{kind}/{sha256}.txt"
    await storage.put(key, data)
    document = Document(
        kind=kind,
        original_filename="pasted.txt",
        sha256=sha256,
        size_bytes=len(data),
        storage_key=key,
        page_count=0,  # not a PDF
        extractor="pasted_text",
        text_storage_key=key,
        char_count=len(normalized),
        is_scanned=False,
    )
    try:
        async with session.begin_nested():  # see ingest_pdf
            await documents_repo.insert(session, document)
        await session.commit()
    except IntegrityError:
        winner = await documents_repo.get_by_hash(session, kind, sha256)
        if winner is None:  # pragma: no cover
            raise
        return winner
    log.info("document_stored", kind=kind, document_id=str(document.id), chars=len(normalized))
    return document


async def load_text(storage: Storage, document: Document) -> str:
    return (await storage.get(document.text_storage_key)).decode("utf-8")
