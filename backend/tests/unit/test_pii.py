from pathlib import Path

import pytest

from app.pipeline.extract import extract_pdf
from app.pipeline.pii import redact

PDFS = Path(__file__).parents[1] / "fixtures" / "pdfs"


def test_real_resume_fixture_is_redacted() -> None:
    text = extract_pdf((PDFS / "resume_single.pdf").read_bytes(), max_pages=20).text
    result = redact(text)
    assert "jordan.avery@example.com" not in result.text
    assert "7700 900123" not in result.text
    assert "linkedin.com" not in result.text
    assert "Jordan" not in result.text and "Avery" not in result.text
    # Country code survives (only location signal in this resume); the number does not.
    assert result.text.startswith("[CANDIDATE]\n[EMAIL] | [PHONE +44] | [URL]")
    assert result.counts == {"email": 1, "url": 1, "phone": 1, "name": 1}
    # Facts the scorer needs must survive.
    for keep in [
        "(2021 - present)",
        "(2018 - 2021)",
        "2k requests/second",
        "60%",
        "7 years",
        "2018",
    ]:
        assert keep in result.text


def test_two_column_fixture() -> None:
    text = extract_pdf((PDFS / "resume_two_column.pdf").read_bytes(), max_pages=20).text
    result = redact(text)
    assert "Sam Rivera" not in result.text
    assert "(555) 010-4477" not in result.text
    assert "sam.rivera@example.org" not in result.text
    assert "github.com/sam-rivera-example" not in result.text
    assert "1B events/day" in result.text and "2020 - present" in result.text


@pytest.mark.parametrize(
    ("phone", "token"),
    [
        ("+1 (415) 555-0132", "[PHONE +1]"),
        ("+44 20 7946 0958", "[PHONE +44]"),
        ("+91-98765-43210", "[PHONE +91]"),
        ("+353.1.555.0199", "[PHONE +353]"),
        ("+919876543210", "[PHONE]"),  # no separator: can't tell where the code ends
        ("415.555.0132", "[PHONE]"),
        ("020 7946 0958", "[PHONE]"),
        ("(555) 010-4477", "[PHONE]"),
    ],
)
def test_phone_formats(phone: str, token: str) -> None:
    result = redact(f"Call {phone} today")
    assert result.text == f"Call {token} today"
    assert result.counts["phone"] == 1


@pytest.mark.parametrize(
    "keep",
    [
        "2018 - 2021",
        "2018-2021",
        "(2019 \u2013 2023)",
        "Python 3.12",
        "3+ years",
        "v1.2.3",
        "ISO 27001",
        "1,000,000 users",
        "99.99% uptime",
        "10.0.0.1",
    ],
)
def test_non_pii_numbers_survive(keep: str) -> None:
    assert redact(f"Worked on {keep} stuff").text == f"Worked on {keep} stuff"


def test_urls() -> None:
    result = redact("See https://example.dev/portfolio and www.example.org or gitlab.com/someone")
    assert result.text == "See [URL] and [URL] or [URL]"


def test_no_name_when_first_lines_are_not_name_like() -> None:
    result = redact("Curriculum vitae of a backend engineer\nPython developer")
    assert result.counts["name"] == 0
    assert result.text.startswith("Curriculum vitae")


@pytest.mark.parametrize(
    "first_line", ["Senior Software Engineer", "Curriculum Vitae", "Data Scientist"]
)
def test_title_line_is_not_taken_as_a_name(first_line: str) -> None:
    text = f"{first_line}\n{first_line}, Northwind (2021 - present)"
    result = redact(text)
    assert result.text == text
    assert result.counts["name"] == 0


def test_name_after_title_line_is_found() -> None:
    result = redact("Resume\nAlex Morgan\nAlex built APIs")
    assert result.text == "Resume\n[CANDIDATE]\n[CANDIDATE] built APIs"
