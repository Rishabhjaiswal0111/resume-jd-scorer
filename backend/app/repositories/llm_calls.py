"""SQL for the llm_calls ledger."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LLMCall


async def insert(session: AsyncSession, call: LLMCall) -> LLMCall:
    session.add(call)
    await session.flush()
    return call


async def find_cache_source(session: AsyncSession, request_hash: str) -> LLMCall | None:
    """Most recent real (non-cache-hit) successful call for this exact request."""
    stmt = (
        select(LLMCall)
        .where(
            LLMCall.request_hash == request_hash,
            LLMCall.status == "success",
            LLMCall.cache_hit.is_(False),
            LLMCall.response_key.is_not(None),
        )
        .order_by(LLMCall.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def sum_cost_for_run(session: AsyncSession, run_id: UUID) -> Decimal:
    stmt = select(func.coalesce(func.sum(LLMCall.cost_usd), 0)).where(LLMCall.run_id == run_id)
    return Decimal((await session.execute(stmt)).scalar_one() or 0)


async def sum_cost_for_rubric(session: AsyncSession, rubric_id: UUID) -> Decimal:
    stmt = select(func.coalesce(func.sum(LLMCall.cost_usd), 0)).where(
        LLMCall.rubric_id == rubric_id, LLMCall.run_id.is_(None)
    )
    return Decimal((await session.execute(stmt)).scalar_one() or 0)


async def list_for_run(session: AsyncSession, run_id: UUID) -> list[LLMCall]:
    stmt = select(LLMCall).where(LLMCall.run_id == run_id).order_by(LLMCall.created_at)
    return list((await session.execute(stmt)).scalars())


async def attach_rubric(session: AsyncSession, call_ids: list[UUID], rubric_id: UUID) -> None:
    if call_ids:
        await session.execute(
            update(LLMCall).where(LLMCall.id.in_(call_ids)).values(rubric_id=rubric_id)
        )
