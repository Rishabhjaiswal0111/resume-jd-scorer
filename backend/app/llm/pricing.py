"""Token usage -> USD (PLAN.md §8). `compute_cost` is pure; price lookup goes via repositories.

Token semantics (OpenRouter / OpenAI usage object, verified against OpenRouter's API
reference): `prompt_tokens` INCLUDES `prompt_tokens_details.cached_tokens`, and
`completion_tokens` INCLUDES `completion_tokens_details.reasoning_tokens`. So:

    cost = (input - cached) * input_price + cached * cached_price + output * output_price
           -------------------------------------------------------------------------------
                                          1,000,000

Anthropic reports uncached, cache-read and cache-write input separately; the client
folds them into the same shape (input = all three, cached = reads) and passes cache
writes in `cache_write_tokens`, billed at 1.25x the input price (5-minute cache).
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import prices as prices_repo

_PER_MILLION = Decimal(1_000_000)
_MONEY_QUANTUM = Decimal("0.00000001")  # NUMERIC(12, 8)
CACHE_WRITE_MULTIPLIER = Decimal("1.25")


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cache_write_tokens: int = 0


@dataclass(frozen=True)
class PriceSnapshot:
    model_price_id: UUID
    input_per_m: Decimal
    cached_input_per_m: Decimal
    output_per_m: Decimal


def split_model_id(model: str) -> tuple[str, str]:
    """'openrouter/deepseek/x' -> ('openrouter', 'deepseek/x')."""
    provider, sep, provider_model = model.partition("/")
    if not sep or not provider_model:
        raise ValueError(f"model must look like '<provider>/<model>', got {model!r}")
    return provider, provider_model


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def compute_cost(usage: Usage, price: PriceSnapshot) -> Decimal:
    if usage.cached_input_tokens + usage.cache_write_tokens > usage.input_tokens:
        raise ValueError("cached + cache-write tokens cannot exceed input_tokens")
    uncached = usage.input_tokens - usage.cached_input_tokens - usage.cache_write_tokens
    total = (
        Decimal(uncached) * price.input_per_m
        + Decimal(usage.cache_write_tokens) * price.input_per_m * CACHE_WRITE_MULTIPLIER
        + Decimal(usage.cached_input_tokens) * price.cached_input_per_m
        + Decimal(usage.output_tokens) * price.output_per_m
    ) / _PER_MILLION
    return quantize_money(total)


async def get_price(
    session: AsyncSession, provider: str, model: str, at: datetime
) -> PriceSnapshot | None:
    row = await prices_repo.get_effective(session, provider, model, at)
    if row is None:
        return None
    return PriceSnapshot(
        model_price_id=row.id,
        input_per_m=row.input_per_m,
        cached_input_per_m=row.cached_input_per_m,
        output_per_m=row.output_per_m,
    )
