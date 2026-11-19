"""Extraction tests on the synthetic PDFs in tests/fixtures/pdfs (make_samples.py)."""

from pathlib import Path

import pytest

from app.core.errors import PdfScannedError, PdfTooLargeError, PdfUnreadableError
from app.pipeline.extract import extract_pdf, junk_ratio, normalize_text

PDFS = Path(__file__).parents[1] / "fixtures" / "pdfs"


def load(name: str) -> bytes:
    return (PDFS / name).read_bytes()


def test_jd_text_and_dehyphenation() -> None:
    result = extract_pdf(load("jd_backend.pdf"), max_pages=20)
    assert result.extractor == "pypdfium2"
    assert result.page_count == 1
    assert not result.is_scanned
    assert result.text.startswith("Senior Backend Engineer (Python)\nAcme Analytics")
    assert "Experience mentoring junior engineers" in result.text  # "Experi-\nence" rejoined
    assert "\r" not in result.text and "\x02" not in result.text


def test_two_column_resume_keeps_columns_together() -> None:
    text = extract_pdf(load("resume_two_column.pdf"), max_pages=20).text
    main = text.index("- Run 40 Kubernetes services in Go and Python")
    next_main = text.index("- Built a Kafka ingestion pipeline (1B events/day)")
    # Sidebar lines must not be interleaved inside the experience section.
    assert text[main:next_main].count("\n") == 1
    assert "Skills\nPython, Go\nPostgreSQL, Redis" in text


def test_multipage_resume() -> None:
    result = extract_pdf(load("resume_multipage.pdf"), max_pages=20)
    assert result.page_count == 2
    assert "Jordan Avery" in result.text and "Achievement line 29" in result.text


def test_page_limit() -> None:
    with pytest.raises(PdfTooLargeError) as exc:
        extract_pdf(load("resume_multipage.pdf"), max_pages=1)
    assert exc.value.details == {"page_count": 2, "max_pages": 1}


def test_scanned_pdf_is_detected() -> None:
    with pytest.raises(PdfScannedError):
        extract_pdf(load("scanned_resume.pdf"), max_pages=20)
    result = extract_pdf(load("scanned_resume.pdf"), max_pages=20, allow_scanned=True)
    assert result.is_scanned and result.text == ""


def test_encrypted_pdf() -> None:
    with pytest.raises(PdfUnreadableError, match="password") as exc:
        extract_pdf(load("encrypted.pdf"), max_pages=20)
    assert exc.value.code == "PDF_UNREADABLE"


def test_corrupt_pdf() -> None:
    with pytest.raises(PdfUnreadableError, match="Couldn't read"):
        extract_pdf(load("corrupt.pdf"), max_pages=20)


def test_not_a_pdf() -> None:
    with pytest.raises(PdfUnreadableError, match="not a PDF"):
        extract_pdf(b"\x89PNG\r\n\x1a\n....", max_pages=20)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ofﬁce  work\r\nnext", "office work\nnext"),  # ligature + CRLF + spaces
        ("Experi\x02ence", "Experience"),
        ("co­operate", "cooperate"),
        ("a\n\n\n\n b \t\n", "a\n\nb"),
        ("x\x00y\x0bz", "xyz"),
    ],
)
def test_normalize_text(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected


def test_junk_ratio() -> None:
    assert junk_ratio("") == 0.0
    assert junk_ratio("abcd") == 0.0
    assert junk_ratio("ab�") == 0.5


# ---- fallback branches (forced via monkeypatch; no natural fixture triggers them) ----

from app.pipeline import extract as extract_module  # noqa: E402


def test_pdfplumber_used_when_pdfium_cannot_open(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_: bytes) -> list[str]:
        raise extract_module.pdfium.PdfiumError("Failed to load document")

    monkeypatch.setattr(extract_module, "_pdfium_pages", boom)
    result = extract_pdf(load("resume_single.pdf"), max_pages=20)
    assert result.extractor == "pdfplumber"
    assert "Jordan Avery" in result.text
    assert result.char_count == len(result.text)


def test_junky_pdfium_text_falls_back_to_cleaner_pdfplumber(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(extract_module, "_pdfium_pages", lambda _: ["" * 50 + "x" * 150])
    result = extract_pdf(load("resume_single.pdf"), max_pages=20)
    assert result.extractor == "pdfplumber"


def test_junky_text_kept_when_fallback_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_: bytes) -> list[str]:
        raise ValueError("plumber broke")

    monkeypatch.setattr(extract_module, "_pdfium_pages", lambda _: ["" * 50 + "x" * 150])
    monkeypatch.setattr(extract_module, "_plumber_pages", boom)
    assert extract_pdf(load("resume_single.pdf"), max_pages=20).extractor == "pypdfium2"


def test_pdf_without_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extract_module, "_pdfium_pages", lambda _: [])
    with pytest.raises(PdfUnreadableError, match="no pages"):
        extract_pdf(load("resume_single.pdf"), max_pages=20)


def test_concurrent_extraction_does_not_crash() -> None:
    """PDFium is not thread-safe; uploads extract in worker threads (asyncio.to_thread)."""
    from concurrent.futures import ThreadPoolExecutor

    data = (PDFS / "resume_two_column.pdf").read_bytes()
    with ThreadPoolExecutor(max_workers=16) as pool:
        texts = list(pool.map(lambda _: extract_pdf(data, max_pages=20).text, range(64)))
    assert len(set(texts)) == 1
