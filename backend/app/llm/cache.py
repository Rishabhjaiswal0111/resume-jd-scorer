"""Request-hash response cache (PLAN.md 1.8), backed by the llm_calls ledger itself.

A request is identified by SHA-256 over the canonical JSON of the full request body
(model + rendered messages + every parameter + output schema). If an identical request
already succeeded, its stored response is reused and a $0 cache-hit row is written.
"""

import hashlib
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import LLMCall
from app.repositories import llm_calls as calls_repo


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def request_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(body).encode()).hexdigest()


async def find_cached(
    sessionmaker: async_sessionmaker[AsyncSession], request_hash_value: str
) -> LLMCall | None:
    async with sessionmaker() as session:
        return await calls_repo.find_cache_source(session, request_hash_value)
