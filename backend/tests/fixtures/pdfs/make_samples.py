"""Regenerate the synthetic sample PDFs used by extraction tests.

    uv run python tests/fixtures/pdfs/make_samples.py

All people, companies and contact details are fictional.
"""

import io
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent
W, H = A4


def _lines(c: canvas.Canvas, x: float, y: float, lines: list[str], size: int = 10) -> float:
    c.setFont("Helvetica", size)
    for line in lines:
        if line.startswith("# "):
            c.setFont("Helvetica-Bold", size + 3)
            c.drawString(x, y, line[2:])
            c.setFont("Helvetica", size)
            y -= size + 8
        else:
            c.drawString(x, y, line)
            y -= size + 4
    return y


def _new(name: str, **kwargs: object) -> canvas.Canvas:
    # invariant=1: fixed dates/ids so regenerated files are byte-identical.
    c = canvas.Canvas(str(OUT / name), pagesize=A4, invariant=1, **kwargs)  # type: ignore[arg-type]
    c.setCreator("jd-scorer test fixtures")
    c.setTitle(name)
    return c


JD = [
    "# Senior Backend Engineer (Python)",
    "Acme Analytics - Remote (EU time zones)",
    "",
    "# About the role",
    "You will design and operate the APIs behind our analytics platform, owning",
    "services end to end: design, implementation, observability and on-call.",
    "",
    "# Requirements",
    "- 5+ years of professional software engineering experience",
    "- 3+ years building production APIs in Python (FastAPI or Django)",
    "- Strong PostgreSQL skills: schema design, query tuning, migrations",
    "- Experience running services on AWS (ECS or Kubernetes)",
    "- Clear written communication in English",
    "",
    "# Nice to have",
    "- Experience with event streaming (Kafka) and data pipelines",
    "- Open-source contributions",
    "- Experi-",
    "ence mentoring junior engineers",
    "",
    "# Not a fit",
    "- Candidates looking for a front-end only role",
]

RESUME_SINGLE = [
    "# Jordan Avery",
    "jordan.avery@example.com | +44 7700 900123 | linkedin.com/in/jordan-avery-example",
    "",
    "# Summary",
    "Backend engineer with 7 years of experience building Python services and data APIs.",
    "",
    "# Experience",
    "Senior Software Engineer, Northwind Data (2021 - present)",
    "- Built FastAPI services handling 2k requests/second on AWS ECS",
    "- Led PostgreSQL schema redesign; cut p95 query latency by 60%",
    "- Mentored three junior engineers",
    "Software Engineer, Contoso Retail (2018 - 2021)",
    "- Django REST APIs for inventory; Kafka consumers for stock events",
    "",
    "# Education",
    "BSc Computer Science, University of Example, 2018",
]

SIDEBAR = [
    "# Contact",
    "sam.rivera@example.org",
    "(555) 010-4477",
    "github.com/sam-rivera-example",
    "",
    "# Skills",
    "Python, Go",
    "PostgreSQL, Redis",
    "Kubernetes, Terraform",
    "Kafka",
    "",
    "# Languages",
    "English, Spanish",
]
MAIN = [
    "# Sam Rivera",
    "Platform Engineer",
    "",
    "# Experience",
    "Platform Engineer, Fabrikam Cloud",
    "2020 - present",
    "- Run 40 Kubernetes services in Go and Python",
    "- Built a Kafka ingestion pipeline (1B events/day)",
    "- On-call lead for the data platform",
    "",
    "Backend Developer, Tailspin Toys",
    "2017 - 2020",
    "- Flask APIs backed by PostgreSQL",
    "",
    "# Education",
    "MEng Software Engineering, 2017",
]


def make_jd() -> None:
    c = _new("jd_backend.pdf")
    _lines(c, 50, H - 60, JD)
    c.save()


def make_resume_single() -> None:
    c = _new("resume_single.pdf")
    _lines(c, 50, H - 60, RESUME_SINGLE)
    c.save()


def make_resume_two_column() -> None:
    c = _new("resume_two_column.pdf")
    c.setFillGray(0.93)
    c.rect(0, 0, 190, H, stroke=0, fill=1)
    c.setFillGray(0)
    # Draw the MAIN column first so content-stream order != visual reading order.
    _lines(c, 215, H - 60, MAIN)
    _lines(c, 25, H - 60, SIDEBAR, size=9)
    c.save()


def make_resume_multipage() -> None:
    c = _new("resume_multipage.pdf")
    _lines(c, 50, H - 60, RESUME_SINGLE)
    c.showPage()
    _lines(
        c,
        50,
        H - 60,
        ["# Projects", "- Open-source maintainer of an example FastAPI plugin (fictional)"]
        + [f"- Achievement line {i}: shipped feature {i} to production" for i in range(1, 30)],
    )
    c.save()


def make_scanned() -> None:
    """A page that is only an image of text: no text layer, like a phone scan."""
    img = Image.new("L", (1240, 1754), 255)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(RESUME_SINGLE):
        draw.text((100, 100 + i * 40), line.lstrip("# "), fill=0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    c = _new("scanned_resume.pdf")
    c.drawImage(ImageReader(io.BytesIO(buf.getvalue())), 0, 0, W, H)
    c.save()


def make_encrypted() -> None:
    c = _new("encrypted.pdf", encrypt="user-password")
    _lines(c, 50, H - 60, RESUME_SINGLE)
    c.save()


def make_corrupt() -> None:
    data = (OUT / "resume_single.pdf").read_bytes()
    (OUT / "corrupt.pdf").write_bytes(data[: len(data) // 3])


if __name__ == "__main__":
    make_jd()
    make_resume_single()
    make_resume_two_column()
    make_resume_multipage()
    make_scanned()
    make_encrypted()
    make_corrupt()
    for p in sorted(OUT.glob("*.pdf")):
        print(f"{p.name:28} {p.stat().st_size:>8} bytes")
