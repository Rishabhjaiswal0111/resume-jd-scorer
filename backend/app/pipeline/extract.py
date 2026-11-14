"""PDF -> normalized text. No LLM, no I/O beyond the bytes passed in.

Strategy (validated against tests/fixtures/pdfs, see test_extract.py):
1. pypdfium2 first. It returns text in content-stream order, which keeps each column of a
   two-column resume together. pdfplumber's default layout interleaves columns line by
   line, so it is only a fallback.
2. pdfplumber is used when pypdfium2 cannot open the file, or its text looks broken
   (high share of replacement / private-use characters) and pdfplumber's is cleaner.
3. Too little text per page => scanned (no text layer). OCR arrives in Phase 5.
"""

import io
import re
import unicodedata
from dataclasses import dataclass

import pdfplumber
import pypdfium2 as pdfium

from app.core.errors import PdfScannedError, PdfTooLargeError, PdfUnreadableError
from app.core.logging import get_logger

log = get_logger(__name__)

PDF_MAGIC = b"%PDF-"
# Average non-whitespace characters per page below which we treat the PDF as scanned.
SCANNED_CHARS_PER_PAGE = 100
# Share of junk characters above which we try the fallback extractor.
JUNK_RATIO_FALLBACK = 0.05


@dataclass(frozen=True)
class Extraction:
    text: str
    page_count: int
    extractor: str  # "pypdfium2" | "pdfplumber"
    is_scanned: bool

    @property
    def char_count(self) -> int:
        return len(self.text)


# pdfium marks a hyphen it joined across a line break as U+0002; U+00AD is a soft hyphen.
_SOFT_HYPHENS = re.compile("[\u0002­]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES = re.compile(r"[ \t\u00a0\u2000-\u200b\u202f\u205f\u3000]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    text = _SOFT_HYPHENS.sub("", text)
    text = unicodedata.normalize("NFKC", text)  # ligatures (ﬁ -> fi), full-width forms
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _BLANK_LINES.sub("\n\n", text).strip()


def junk_ratio(text: str) -> float:
    """Share of characters that signal a broken text layer (missing ToUnicode maps etc.)."""
    if not text:
        return 0.0
    junk = sum(1 for ch in text if ch == "�" or unicodedata.category(ch) in ("Co", "Cn", "Cs"))
    return junk / len(text)


def _meaningful_chars(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def _pdfium_pages(data: bytes) -> list[str]:
    doc = pdfium.PdfDocument(data)
    try:
        pages: list[str] = []
        for index in range(len(doc)):
            page = doc[index]
            textpage = page.get_textpage()
            try:
                pages.append(textpage.get_text_bounded())
            finally:
                textpage.close()
                page.close()
        return pages
    finally:
        doc.close()


def _plumber_pages(data: bytes) -> list[str]:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def _unreadable(error: Exception) -> PdfUnreadableError:
    if "password" in str(error).lower():
        return PdfUnreadableError("This PDF is password-protected", details={"reason": "encrypted"})
    return PdfUnreadableError("Couldn't read this PDF", details={"reason": type(error).__name__})


def extract_pdf(data: bytes, *, max_pages: int, allow_scanned: bool = False) -> Extraction:
    """Extract and normalize text. Raises PDF_UNREADABLE / PDF_TOO_LARGE / PDF_SCANNED."""
    if not data.startswith(PDF_MAGIC):
        raise PdfUnreadableError("File is not a PDF", details={"reason": "bad_magic"})

    extractor = "pypdfium2"
    try:
        pages = _pdfium_pages(data)
    except pdfium.PdfiumError as primary_error:
        log.info("pdfium_failed", error=str(primary_error))
        try:
            pages = _plumber_pages(data)
            extractor = "pdfplumber"
        except Exception as fallback_error:
            log.info("pdfplumber_failed", error=type(fallback_error).__name__)
            raise _unreadable(primary_error) from primary_error

    page_count = len(pages)
    if page_count == 0:
        raise PdfUnreadableError("PDF has no pages", details={"reason": "no_pages"})
    if page_count > max_pages:
        raise PdfTooLargeError(
            f"PDF has {page_count} pages; the limit is {max_pages}",
            details={"page_count": page_count, "max_pages": max_pages},
        )

    text = normalize_text("\n\n".join(pages))
    if extractor == "pypdfium2" and junk_ratio(text) > JUNK_RATIO_FALLBACK:
        try:
            alt = normalize_text("\n\n".join(_plumber_pages(data)))
        except Exception as error:
            log.info("pdfplumber_fallback_failed", error=type(error).__name__)
        else:
            if junk_ratio(alt) < junk_ratio(text):
                text, extractor = alt, "pdfplumber"

    is_scanned = _meaningful_chars(text) / page_count < SCANNED_CHARS_PER_PAGE
    log.info(
        "pdf_extracted",
        extractor=extractor,
        page_count=page_count,
        char_count=len(text),
        is_scanned=is_scanned,
    )
    if is_scanned and not allow_scanned:
        raise PdfScannedError(
            "This looks like a scanned PDF (no text layer); OCR is not enabled yet",
            details={"page_count": page_count, "char_count": len(text)},
        )
    return Extraction(text=text, page_count=page_count, extractor=extractor, is_scanned=is_scanned)
