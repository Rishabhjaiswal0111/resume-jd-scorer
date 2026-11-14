"""History endpoints: completed runs grouped by JD; replays and failed runs excluded."""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.errors import PdfScannedError
from app.llm.client import LLMClient
from app.main import create_app
from app.services.scoring_service import PdfInput, ScoringService
from tests.conftest import DbContext
from tests.fakes import HAIKU, FakeAnthropic, claude_message, seed_haiku_price

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parents[1] / "fixtures"


def pdf(name: str) -> PdfInput:
    return PdfInput(name, (FIXTURES / "pdfs" / name).read_bytes())


async def test_history_groups_completed_runs_by_jd(db: DbContext) -> None:
    db.settings.anthropic_api_key = SecretStr("k")
    await seed_haiku_price(db.sessionmaker)
    rubric = json.loads((FIXTURES / "llm" / "synthetic_jd_backend.rubric.json").read_text())
    evaluation = json.loads(
        (FIXTURES / "llm" / "synthetic_resume_single.evaluation.json").read_text()
    )
    # Rubric once (cached per JD), then one evaluation per resume.
    fake = FakeAnthropic(
        claude_message(rubric), claude_message(evaluation), claude_message(evaluation)
    )
    client = LLMClient(db.settings, db.sessionmaker, db.storage, anthropic_transport=fake.transport)
    service = ScoringService(db.settings, db.sessionmaker, db.storage, client)

    first = await service.score_pdfs(pdf("jd_backend.pdf"), pdf("resume_single.pdf"), model=HAIKU)
    second = await service.score_pdfs(
        pdf("jd_backend.pdf"), pdf("resume_two_column.pdf"), model=HAIKU
    )
    await service.replay(first.id)  # replays are not history entries
    with pytest.raises(PdfScannedError):  # failed runs are not history entries
        await service.score_pdfs(pdf("jd_backend.pdf"), pdf("scanned_resume.pdf"), model=HAIKU)

    app = create_app(db.settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        jds = (await http.get("/api/v1/jds")).json()
        runs = (
            await http.get("/api/v1/runs", params={"jd_document_id": jds[0]["jd_document_id"]})
        ).json()
        all_runs = (await http.get("/api/v1/runs")).json()
        bad = await http.get("/api/v1/runs", params={"limit": 0})

    assert len(jds) == 1
    assert jds[0]["title"] == "Senior Backend Engineer (Python)"
    assert (jds[0]["source"], jds[0]["filename"]) == ("pdf", "jd_backend.pdf")
    assert (jds[0]["run_count"], jds[0]["best_score"]) == (2, "90")
    assert [r["id"] for r in runs] == [str(second.id), str(first.id)]  # newest first
    assert [r["resume_filename"] for r in runs] == ["resume_two_column.pdf", "resume_single.pdf"]
    assert {r["verdict"] for r in runs} == {"Strong fit"}
    assert "cost" not in runs[0] and "model" not in runs[0]  # user-facing: no admin data
    assert len(all_runs) == 2
    assert bad.status_code == 422
