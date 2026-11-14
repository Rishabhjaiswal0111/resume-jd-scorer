"""Keep model_prices in sync with the provider's published prices (PLAN.md §8, 1.1).

OpenRouter publishes per-token USD prices at GET /api/v1/models (no key required):
`pricing.prompt`, `pricing.completion`, `pricing.input_cache_read`. We store USD per 1M
tokens and add a new row only when a price actually changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.core.logging import get_logger
from app.repositories import prices as prices_repo

log = get_logger(__name__)
_MILLION = Decimal(1_000_000)
OPENROUTER_MODELS_DOC = "https://openrouter.ai/api/v1/models"

# Anthropic publishes no prices API. Values copied from the pricing page on 2026-11-14
# (USD per 1M tokens, prompts <= 100K tokens). Re-check the page when changing these.
ANTHROPIC_PRICING_DOC = "https://platform.claude.com/docs/en/about-claude/pricing"
ANTHROPIC_PRICES: dict[str, tuple[str, str, str]] = {
    # model: (input, cache read, output)
    "claude-haiku-5-5": ("0.10", "0.01", "0.50"),
}


def anthropic_price(model: str) -> PublishedPrice:
    if model not in ANTHROPIC_PRICES:
        raise NotFoundError(
            f"No published price recorded for anthropic/{model}; add it to ANTHROPIC_PRICES",
            code="MODEL_NOT_FOUND",
        )
    input_per_m, cached, output = (Decimal(v) for v in ANTHROPIC_PRICES[model])
    return PublishedPrice(
        provider="anthropic",
        model=model,
        input_per_m=input_per_m,
        cached_input_per_m=cached,
        output_per_m=output,
        source_url=ANTHROPIC_PRICING_DOC,
    )


@dataclass(frozen=True)
class PublishedPrice:
    provider: str
    model: str
    input_per_m: Decimal
    cached_input_per_m: Decimal
    output_per_m: Decimal
    source_url: str


def _per_million(value: Any) -> Decimal:
    return (Decimal(str(value or 0)) * _MILLION).normalize()


def parse_openrouter_models(payload: dict[str, Any], model: str) -> PublishedPrice:
    for entry in payload.get("data", []):
        if entry.get("id") == model:
            pricing = entry.get("pricing") or {}
            input_per_m = _per_million(pricing.get("prompt"))
            cached = pricing.get("input_cache_read")
            return PublishedPrice(
                provider="openrouter",
                model=model,
                input_per_m=input_per_m,
                # No cache price published => cached tokens bill at the normal input price.
                cached_input_per_m=_per_million(cached) if cached is not None else input_per_m,
                output_per_m=_per_million(pricing.get("completion")),
                source_url=OPENROUTER_MODELS_DOC,
            )
    raise NotFoundError(f"Model {model!r} is not listed by OpenRouter", code="MODEL_NOT_FOUND")


async def fetch_openrouter_price(
    settings: Settings, model: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> PublishedPrice:
    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url, timeout=30, transport=transport
    ) as http:
        response = await http.get("/models")
    if response.status_code != 200:
        raise AppError(
            f"OpenRouter /models returned HTTP {response.status_code}", code="PRICE_FETCH_FAILED"
        )
    return parse_openrouter_models(response.json(), model)


@dataclass(frozen=True)
class SyncResult:
    price: PublishedPrice
    changed: bool


async def upsert_price(
    session: AsyncSession, price: PublishedPrice, *, now: datetime | None = None
) -> SyncResult:
    current = await prices_repo.get_current(session, price.provider, price.model)
    if current is not None and (
        current.input_per_m == price.input_per_m
        and current.cached_input_per_m == price.cached_input_per_m
        and current.output_per_m == price.output_per_m
    ):
        return SyncResult(price=price, changed=False)
    await prices_repo.add_price(
        session,
        provider=price.provider,
        model=price.model,
        input_per_m=price.input_per_m,
        cached_input_per_m=price.cached_input_per_m,
        output_per_m=price.output_per_m,
        effective_from=now or datetime.now(UTC),
        source_url=price.source_url,
    )
    log.info(
        "model_price_added",
        provider=price.provider,
        model=price.model,
        input_per_m=str(price.input_per_m),
        cached_input_per_m=str(price.cached_input_per_m),
        output_per_m=str(price.output_per_m),
    )
    return SyncResult(price=price, changed=True)
