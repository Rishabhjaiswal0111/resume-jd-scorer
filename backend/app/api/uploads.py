"""Reading uploads and serving stored files back (shared by the routers)."""

from urllib.parse import quote

from fastapi import Response, UploadFile

from app.core.config import Settings
from app.core.errors import PdfTooLargeError, ValidationFailedError
from app.db.models import Document
from app.schemas.workspace import UploadError
from app.services.candidate_service import ResumeFile
from app.services.scoring_service import PdfInput

MAX_FILES_PER_UPLOAD = 50


async def read_pdf(upload: UploadFile, settings: Settings) -> PdfInput:
    # Read one byte past the limit so oversized files are rejected without buffering them all.
    data = await upload.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise PdfTooLargeError(
            f"{upload.filename} is larger than {settings.max_upload_bytes // (1024 * 1024)} MB",
            details={"max_bytes": settings.max_upload_bytes},
        )
    return PdfInput(upload.filename or "upload.pdf", data)


async def read_resumes(
    uploads: list[UploadFile], settings: Settings
) -> tuple[list[ResumeFile], list[UploadError]]:
    if len(uploads) > MAX_FILES_PER_UPLOAD:
        raise ValidationFailedError(f"Upload at most {MAX_FILES_PER_UPLOAD} resumes at a time")
    files, errors = [], []
    for upload in uploads:
        try:
            pdf = await read_pdf(upload, settings)
        except PdfTooLargeError as error:
            errors.append(
                UploadError(filename=upload.filename or "?", code=error.code, message=error.message)
            )
            continue
        files.append(ResumeFile(pdf.filename, pdf.data))
    return files, errors


def inline_file(document: Document, data: bytes) -> Response:
    """Shown in the browser (inline), never executed: PDFs as PDF, pasted text as plain text."""
    pasted = document.extractor == "pasted_text"
    filename = document.original_filename
    return Response(
        content=data,
        media_type="text/plain; charset=utf-8" if pasted else "application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=300",
        },
    )
