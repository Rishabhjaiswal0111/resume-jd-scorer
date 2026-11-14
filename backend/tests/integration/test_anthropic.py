"""Claude (Anthropic SDK) path: request shape, usage -> cost, refusal, retries, full run."""

import json
from decimal import Decimal
from pathlib import Path

import httpx2
import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core.errors import LLMRefusedError
from app.db.models import LLMCall
from app.llm.client import LLMClient
from app.services.scoring_service import PdfInput, ScoringService
from tests.conftest import DbContext
from tests.fakes import HAIKU, FakeAnthropic, claude_message, seed_haiku_price

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parents[1] / "fixtures"


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    count: int


def make_client(db: DbContext, fake: FakeAnthropic) -> LLMClient:
    return LLMClient(db.settings, db.sessionmaker, db.storage, anthropic_transport=fake.transport)


async def ask(db: DbContext, fake: FakeAnthropic) -> object:
    return await make_client(db, fake).complete_json(
        purpose="eval",
        prompt_version="test.v1",
        messages=[{"role": "system", "content": "be terse"}, {"role": "user", "content": "hi"}],
        output_model=Answer,
        schema_name="answer",
        model=HAIKU,
    )


async def ledger(db: DbContext) -> list[LLMCall]:
    async with db.sessionmaker() as session:
        return list((await session.execute(select(LLMCall).order_by(LLMCall.created_at))).scalars())


async def test_success_request_shape_and_cost(
    db: DbContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        db.settings, "anthropic_api_key", type(db.settings.openrouter_api_key)("sk-ant-test")
    )
    await seed_haiku_price(db.sessionmaker)
    fake = FakeAnthropic(
        claude_message(
            {"title": "x", "count": 2},
            input_tokens=1500,
            cache_read=500,
            output_tokens=800,
            thinking_tokens=300,
        )
    )
    result = await ask(db, fake)
    assert result.value == Answer(title="x", count=2)  # type: ignore[attr-defined]
    # (1500 * 0.10 + 500 * 0.01 + 800 * 0.50) / 1e6 = 0.000555
    assert result.cost_usd == Decimal("0.000555")  # type: ignore[attr-defined]

    [body] = fake.requests
    assert body["model"] == "claude-haiku-5-5"
    assert body["system"] == "be terse"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["effort"] == "medium"
    assert "temperature" not in body and "seed" not in body
    assert fake.headers[0]["authorization"] == "Bearer sk-ant-test"  # anthropic SDK 2.x

    [row] = await ledger(db)
    assert (row.provider, row.model, row.status) == ("anthropic", "claude-haiku-5-5", "success")
    assert (row.input_tokens, row.cached_input_tokens, row.output_tokens, row.reasoning_tokens) == (
        2000,
        500,
        800,
        300,
    )
    assert row.provider_request_id == "msg_test"
    assert row.provider_reported_cost_usd is None  # Anthropic reports no cost in the response


async def test_refusal_is_recorded_and_not_retried(
    db: DbContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db.settings, "anthropic_api_key", type(db.settings.openrouter_api_key)("k"))
    await seed_haiku_price(db.sessionmaker)
    fake = FakeAnthropic(claude_message("", output_tokens=5, stop_reason="refusal"))
    with pytest.raises(LLMRefusedError):
        await ask(db, fake)
    [row] = await ledger(db)
    assert (row.status, row.error_code) == ("error", "LLM_REFUSED")
    assert row.cost_usd == Decimal("0.0002025")  # (2000*0.10 + 5*0.50)/1e6


async def test_overloaded_529_is_retried(db: DbContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db.settings, "anthropic_api_key", type(db.settings.openrouter_api_key)("k"))
    await seed_haiku_price(db.sessionmaker)
    fake = FakeAnthropic(
        httpx2.Response(
            529, json={"type": "error", "error": {"type": "overloaded_error", "message": "busy"}}
        ),
        claude_message({"title": "x", "count": 1}),
    )
    await ask(db, fake)
    assert [(r.status, r.error_code) for r in await ledger(db)] == [
        ("error", "LLM_PROVIDER_ERROR"),
        ("success", None),
    ]


async def test_full_scoring_run_on_haiku(db: DbContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db.settings, "anthropic_api_key", type(db.settings.openrouter_api_key)("k"))
    await seed_haiku_price(db.sessionmaker)
    rubric = json.loads((FIXTURES / "llm" / "synthetic_jd_backend.rubric.json").read_text())
    evaluation = json.loads(
        (FIXTURES / "llm" / "synthetic_resume_single.evaluation.json").read_text()
    )
    fake = FakeAnthropic(claude_message(rubric), claude_message(evaluation))
    client = make_client(db, fake)
    service = ScoringService(db.settings, db.sessionmaker, db.storage, client)
    run = await service.score_pdfs(
        PdfInput("jd.pdf", (FIXTURES / "pdfs" / "jd_backend.pdf").read_bytes()),
        PdfInput("cv.pdf", (FIXTURES / "pdfs" / "resume_single.pdf").read_bytes()),
        model=HAIKU,
    )
    assert run.status == "completed"
    assert run.score == Decimal("89.88")  # same grades as the OpenRouter flow test
    assert run.llm_cost_usd == Decimal("0.0006")  # (2000*0.10 + 800*0.50)/1e6
    assert run.model == HAIKU
