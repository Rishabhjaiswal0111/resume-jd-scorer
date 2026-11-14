"""LLM client + ledger + cache against real Postgres and a scripted fake OpenRouter."""

from decimal import Decimal

import httpx
import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core.errors import (
    LLMInvalidOutputError,
    LLMNotConfiguredError,
    LLMRateLimitedError,
    LLMRequestRejectedError,
    LLMTimeoutError,
    PriceMissingError,
)
from app.db.models import LLMCall
from app.llm.client import LLMClient, llm_json_schema
from app.schemas.rubric import RubricOutput
from tests.conftest import DbContext
from tests.fakes import MODEL, FakeOpenRouter, completion, seed_price

pytestmark = pytest.mark.integration


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    count: int


async def ask(db: DbContext, fake: FakeOpenRouter, **kwargs: object) -> object:
    client = LLMClient(db.settings, db.sessionmaker, db.storage, transport=fake.transport)
    params: dict[str, object] = {
        "purpose": "eval",
        "prompt_version": "test.v1",
        "messages": [{"role": "user", "content": "hi"}],
        "output_model": Answer,
        "schema_name": "answer",
        "model": MODEL,
    }
    params.update(kwargs)
    return await client.complete_json(**params)  # type: ignore[arg-type]


async def ledger(db: DbContext) -> list[LLMCall]:
    async with db.sessionmaker() as session:
        return list((await session.execute(select(LLMCall).order_by(LLMCall.created_at))).scalars())


async def test_success_records_exact_cost_and_provider_cost(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = FakeOpenRouter().add(
        "answer",
        completion(
            {"title": "x", "count": 2},
            prompt_tokens=1000,
            cached_tokens=300,
            completion_tokens=200,
            reasoning_tokens=50,
            cost=0.0000763542,
            gen_id="gen-abc",
        ),
    )
    result = await ask(db, fake)

    # (700 * 0.0507 + 300 * 0.001014 + 200 * 0.2028) / 1e6 = 0.0000763542 -> 0.00007635
    assert result.cost_usd == Decimal("0.00007635")  # type: ignore[attr-defined]
    assert result.value == Answer(title="x", count=2)  # type: ignore[attr-defined]
    [row] = await ledger(db)
    assert (row.status, row.purpose, row.provider, row.model) == (
        "success",
        "eval",
        "openrouter",
        "deepseek/deepseek-v4.1-flash",
    )
    assert (row.input_tokens, row.cached_input_tokens, row.output_tokens, row.reasoning_tokens) == (
        1000,
        300,
        200,
        50,
    )
    assert row.price_input_per_m == Decimal("0.0507")
    assert row.provider_reported_cost_usd == Decimal("0.00007635")
    assert row.cost_delta_usd == Decimal(0)
    assert row.provider_request_id == "gen-abc"
    assert row.request_key and row.response_key
    stored = await db.storage.get(row.request_key)
    assert b'"strict": true' in stored


async def test_request_body_shape(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = FakeOpenRouter().add("answer", completion({"title": "x", "count": 1}))
    await ask(db, fake)
    [body] = fake.requests
    assert body["model"] == "deepseek/deepseek-v4.1-flash"
    assert body["temperature"] == 0 and body["seed"] == 7
    assert body["provider"] == {"require_parameters": True, "data_collection": "deny"}
    assert body["response_format"]["json_schema"]["strict"] is True
    assert fake.headers[0]["authorization"] == "Bearer sk-or-test"


async def test_retry_on_429_then_success_writes_one_row_per_attempt(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = FakeOpenRouter().add(
        "answer",
        httpx.Response(429, json={"error": {"message": "slow down"}}),
        httpx.Response(502, text="bad gateway"),
        completion({"title": "x", "count": 1}),
    )
    await ask(db, fake)
    rows = await ledger(db)
    assert [(r.attempt, r.status, r.error_code) for r in rows] == [
        (1, "error", "LLM_RATE_LIMITED"),
        (2, "error", "LLM_PROVIDER_ERROR"),
        (3, "success", None),
    ]
    assert [r.cost_usd for r in rows[:2]] == [Decimal(0), Decimal(0)]


async def test_timeouts_exhaust_retries(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = FakeOpenRouter().add("answer", *[httpx.ReadTimeout("slow")] * 4)
    with pytest.raises(LLMTimeoutError):
        await ask(db, fake)
    rows = await ledger(db)
    assert [r.attempt for r in rows] == [1, 2, 3, 4]  # LLM_MAX_RETRIES=3 -> 4 attempts
    assert {r.error_code for r in rows} == {"LLM_TIMEOUT"}


async def test_rate_limit_exhaustion_raises(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = FakeOpenRouter().add("answer", *[httpx.Response(429, headers={"retry-after": "0"})] * 4)
    with pytest.raises(LLMRateLimitedError):
        await ask(db, fake)


async def test_4xx_is_not_retried(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = FakeOpenRouter().add(
        "answer", httpx.Response(404, json={"error": {"message": "No endpoints found"}})
    )
    with pytest.raises(LLMRequestRejectedError, match="No endpoints found"):
        await ask(db, fake)
    assert len(await ledger(db)) == 1


async def test_error_inside_200_body_is_a_provider_error(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = FakeOpenRouter().add(
        "answer",
        {"error": {"message": "upstream failed", "code": 502}},
        completion({"title": "x", "count": 1}),
    )
    await ask(db, fake)
    assert [r.status for r in await ledger(db)] == ["error", "success"]


async def test_invalid_output_is_recorded_with_its_cost(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = FakeOpenRouter().add("answer", completion({"title": "x"}, completion_tokens=10))
    with pytest.raises(LLMInvalidOutputError) as exc:
        await ask(db, fake)
    assert exc.value.raw_text == '{"title": "x"}'
    [row] = await ledger(db)
    assert row.status == "invalid_output"
    assert row.cost_usd is not None and row.cost_usd > 0  # tokens were spent


async def test_truncated_output_is_invalid(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = FakeOpenRouter().add(
        "answer", completion({"title": "x", "count": 1}, finish_reason="length")
    )
    with pytest.raises(LLMInvalidOutputError):
        await ask(db, fake)


async def test_code_fenced_json_is_accepted(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = FakeOpenRouter().add("answer", completion('```json\n{"title": "x", "count": 3}\n```'))
    assert (await ask(db, fake)).value.count == 3  # type: ignore[attr-defined]


async def test_cache_hit_records_zero_cost_row(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = FakeOpenRouter().add("answer", completion({"title": "x", "count": 1}))
    first = await ask(db, fake)
    second = await ask(db, fake)  # no second scripted response: must not hit HTTP
    assert second.cache_hit and second.value == first.value  # type: ignore[attr-defined]
    rows = await ledger(db)
    assert [(r.cache_hit, r.cost_usd) for r in rows] == [
        (False, first.cost_usd),  # type: ignore[attr-defined]
        (True, Decimal(0)),
    ]
    assert rows[1].cache_source_call_id == rows[0].id
    assert rows[1].input_tokens == rows[0].input_tokens
    assert len(fake.requests) == 1


async def test_missing_price_fails_before_spending(db: DbContext) -> None:
    fake = FakeOpenRouter()
    with pytest.raises(PriceMissingError):
        await ask(db, fake)
    assert fake.requests == [] and await ledger(db) == []


async def test_missing_api_key(db: DbContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db.settings, "openrouter_api_key", None)
    with pytest.raises(LLMNotConfiguredError, match="OPENROUTER_API_KEY"):
        await ask(db, FakeOpenRouter())


async def test_unsupported_provider(db: DbContext) -> None:
    with pytest.raises(LLMNotConfiguredError, match="not supported"):
        await ask(db, FakeOpenRouter(), model="deepseek/deepseek-chat")


def test_llm_schema_is_strict_and_keeps_field_named_title() -> None:
    schema = llm_json_schema(RubricOutput)
    assert "$defs" not in schema
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["title", "role_summary", "core_requirement", "criteria"]
    assert "title" in schema["properties"]  # a field called "title" is not a keyword
    item = schema["properties"]["criteria"]["items"]
    assert item["additionalProperties"] is False
    assert "pattern" not in item["properties"]["key"]
    assert item["properties"]["operator"]["enum"][0] == "must_have"
