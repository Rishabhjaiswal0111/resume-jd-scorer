"""HTTP: POST /score with real PDFs (fake Claude), GET /runs/{id}, error shape."""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.api.v1.runs import get_scoring_service
from app.llm.client import LLMClient
from app.main import create_app
from app.services.scoring_service import ScoringService
from tests.conftest import DbContext
from tests.fakes import HAIKU, FakeAnthropic, claude_message, seed_haiku_price

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parents[1] / "fixtures"


def files(resume: str = "resume_single.pdf") -> dict[str, tuple[str, bytes, str]]:
    return {
        "jd": ("jd.pdf", (FIXTURES / "pdfs" / "jd_backend.pdf").read_bytes(), "application/pdf"),
        "resume": ("cv.pdf", (FIXTURES / "pdfs" / resume).read_bytes(), "application/pdf"),
    }


async def post_score(db: DbContext, fake: FakeAnthropic, **kwargs: object):  # type: ignore[no-untyped-def]
    db.settings.anthropic_api_key = SecretStr("k")
    db.settings.llm_default_model = HAIKU
    app = create_app(db.settings)
    client = LLMClient(db.settings, db.sessionmaker, db.storage, anthropic_transport=fake.transport)
    app.dependency_overrides[get_scoring_service] = lambda: ScoringService(
        db.settings, db.sessionmaker, db.storage, client
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        res = await http.post("/api/v1/score", files=files(**kwargs))  # type: ignore[arg-type]
        again = None
        if res.status_code == 200:
            again = await http.get(f"/api/v1/runs/{res.json()['id']}")
        return res, again


async def test_score_returns_full_run(db: DbContext) -> None:
    await seed_haiku_price(db.sessionmaker)
    rubric = json.loads((FIXTURES / "llm" / "synthetic_jd_backend.rubric.json").read_text())
    evaluation = json.loads(
        (FIXTURES / "llm" / "synthetic_resume_single.evaluation.json").read_text()
    )
    res, again = await post_score(
        db, FakeAnthropic(claude_message(rubric), claude_message(evaluation))
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "completed"
    assert body["score"] == "89.88"
    assert body["role_title"] == "Senior Backend Engineer (Python)"
    assert body["role_overlap"]["level"] == "Strong"
    assert [c["key"] for c in body["criteria"]][:2] == ["c_years_experience", "c_python_apis"]
    english = next(c for c in body["criteria"] if c["key"] == "c_written_english")
    assert (english["outcome"], english["forced"]) == ("Fail", "fail_no_evidence")
    assert english["name"] == "Clear written English"
    assert body["cost"] == {
        "run_llm_cost_usd": "0.0006",
        "rubric_cost_share_usd": "0.0006",
        "provider_reported_usd": None,
        "llm_calls": 1,
    }
    assert again is not None and again.json() == body


async def test_scanned_resume_returns_error_with_run_id(db: DbContext) -> None:
    await seed_haiku_price(db.sessionmaker)
    res, _ = await post_score(db, FakeAnthropic(), resume="scanned_resume.pdf")
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "PDF_SCANNED"
    assert len(error["details"]["run_id"]) == 36
    assert error["request_id"] == res.headers["x-request-id"]


async def test_unknown_run_is_404(db: DbContext) -> None:
    app = create_app(db.settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        res = await http.get("/api/v1/runs/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
