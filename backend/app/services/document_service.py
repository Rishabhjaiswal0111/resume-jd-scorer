"""Store an uploaded PDF + its extracted text, deduplicated by (kind, sha256)."""

import asyncio
import hashlib

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import PdfTooLargeError
from app.core.logging import get_logger
from app.db.models import Document
from app.pipeline.extract import extract_pdf
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
        await documents_repo.insert(session, document)
        await session.commit()
    except IntegrityError:
        # Same file uploaded concurrently: the other insert won; use its row.
        await session.rollback()
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


async def load_text(storage: Storage, document: Document) -> str:
    return (await storage.get(document.text_storage_key)).decode("utf-8")
