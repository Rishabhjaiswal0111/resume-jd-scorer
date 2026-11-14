"""Cost ledger writer (PLAN.md §8).

Every LLM attempt (success, failure, cache hit) becomes one llm_calls row, written in its
OWN short transaction so the row survives even if the surrounding business transaction
rolls back. Money spent is money spent.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import LLMCall
from app.llm.pricing import PriceSnapshot, Usage
from app.repositories import llm_calls as calls_repo


@dataclass
class LedgerEntry:
    purpose: str
    provider: str
    model: str
    prompt_version: str
    request_hash: str
    status: str
    attempt: int
    run_id: UUID | None = None
    rubric_id: UUID | None = None
    usage: Usage | None = None
    price: PriceSnapshot | None = None
    cost_usd: Decimal | None = None
    provider_reported_cost_usd: Decimal | None = None
    provider_request_id: str | None = None
    cache_hit: bool = False
    cache_source_call_id: UUID | None = None
    error_code: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    request_key: str | None = None
    response_key: str | None = None
    id: UUID | None = None


class Ledger:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    @staticmethod
    def new_id() -> UUID:
        return uuid4()

    async def record(self, entry: LedgerEntry) -> UUID:
        fields = asdict(entry)
        usage = fields.pop("usage")
        price = fields.pop("price")
        call = LLMCall(**{k: v for k, v in fields.items() if k != "id"}, id=entry.id or uuid4())
        if usage is not None:
            call.input_tokens = usage["input_tokens"]
            call.cached_input_tokens = usage["cached_input_tokens"]
            call.output_tokens = usage["output_tokens"]
            call.reasoning_tokens = usage["reasoning_tokens"]
        if price is not None:
            call.model_price_id = price["model_price_id"]
            call.price_input_per_m = price["input_per_m"]
            call.price_cached_per_m = price["cached_input_per_m"]
            call.price_output_per_m = price["output_per_m"]
        async with self._sessionmaker() as session, session.begin():
            await calls_repo.insert(session, call)
        return call.id
