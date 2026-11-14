"""A scripted fake of OpenRouter's /chat/completions, used via httpx.MockTransport.

Response bodies follow the shape documented in OpenRouter's API reference
(id, choices[].message.content, finish_reason, usage{prompt_tokens, completion_tokens,
prompt_tokens_details.cached_tokens, completion_tokens_details.reasoning_tokens, cost}).
"""

import json
from collections import defaultdict, deque
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories import prices as prices_repo

PRICE = {"input": Decimal("0.0507"), "cached": Decimal("0.001014"), "output": Decimal("0.2028")}
MODEL = "openrouter/deepseek/deepseek-v4.1-flash"
PROVIDER_MODEL = "deepseek/deepseek-v4.1-flash"


def completion(
    content: Any,
    *,
    prompt_tokens: int = 1000,
    completion_tokens: int = 200,
    cached_tokens: int = 0,
    reasoning_tokens: int = 0,
    cost: float | None = None,
    finish_reason: str = "stop",
    gen_id: str = "gen-test",
) -> dict[str, Any]:
    text = content if isinstance(content, str) else json.dumps(content)
    usage: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "prompt_tokens_details": {"cached_tokens": cached_tokens},
        "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
    }
    if cost is not None:
        usage["cost"] = cost
    return {
        "id": gen_id,
        "object": "chat.completion",
        "model": PROVIDER_MODEL,
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": text},
            }
        ],
        "usage": usage,
    }


Scripted = dict[str, Any] | httpx.Response | Exception


class FakeOpenRouter:
    """Queue responses per schema name ("rubric", "evaluation", ...); records every request."""

    def __init__(self) -> None:
        self.queues: dict[str, deque[Scripted]] = defaultdict(deque)
        self.requests: list[dict[str, Any]] = []
        self.headers: list[httpx.Headers] = []

    def add(self, schema_name: str, *responses: Scripted) -> "FakeOpenRouter":
        self.queues[schema_name].extend(responses)
        return self

    def calls_for(self, schema_name: str) -> list[dict[str, Any]]:
        return [
            r for r in self.requests if r["response_format"]["json_schema"]["name"] == schema_name
        ]

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions"), request.url
        body = json.loads(request.content)
        self.requests.append(body)
        self.headers.append(request.headers)
        name = body["response_format"]["json_schema"]["name"]
        if not self.queues[name]:
            raise AssertionError(f"unexpected extra LLM call for schema {name!r}")
        scripted = self.queues[name].popleft()
        if isinstance(scripted, Exception):
            raise scripted
        if isinstance(scripted, httpx.Response):
            return scripted
        return httpx.Response(200, json=scripted)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


async def seed_price(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as session:
        await prices_repo.add_price(
            session,
            provider="openrouter",
            model=PROVIDER_MODEL,
            input_per_m=PRICE["input"],
            cached_input_per_m=PRICE["cached"],
            output_per_m=PRICE["output"],
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
            source_url="test",
        )
        await session.commit()


# ---------------------------------------------------------------- Anthropic

import httpx2  # noqa: E402

HAIKU = "anthropic/claude-haiku-5-5"


def claude_message(
    content: Any,
    *,
    input_tokens: int = 2000,
    output_tokens: int = 800,
    cache_read: int = 0,
    thinking_tokens: int = 0,
    stop_reason: str = "end_turn",
    msg_id: str = "msg_test",
) -> dict[str, Any]:
    """A Messages API response body: thinking block first, then the JSON text block."""
    text = content if isinstance(content, str) else json.dumps(content)
    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "content": [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "text", "text": text},
        ],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": 0,
            "output_tokens_details": {"thinking_tokens": thinking_tokens},
        },
    }


class FakeAnthropic:
    """Serves scripted responses in order; records request bodies and headers."""

    def __init__(self, *responses: dict[str, Any] | httpx2.Response) -> None:
        self.queue: deque[dict[str, Any] | httpx2.Response] = deque(responses)
        self.requests: list[dict[str, Any]] = []
        self.headers: list[Any] = []

    def add(self, *responses: dict[str, Any] | httpx2.Response) -> "FakeAnthropic":
        self.queue.extend(responses)
        return self

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        assert request.url.path.endswith("/v1/messages"), request.url
        self.requests.append(json.loads(request.content))
        self.headers.append(request.headers)
        if not self.queue:
            raise AssertionError("unexpected extra Claude call")
        scripted = self.queue.popleft()
        if isinstance(scripted, httpx2.Response):
            return scripted
        return httpx2.Response(200, json=scripted)

    @property
    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self.handler)


async def seed_haiku_price(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as session:
        await prices_repo.add_price(
            session,
            provider="anthropic",
            model="claude-haiku-5-5",
            input_per_m=Decimal("0.10"),
            cached_input_per_m=Decimal("0.01"),
            output_per_m=Decimal("0.50"),
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
            source_url="test",
        )
        await session.commit()
