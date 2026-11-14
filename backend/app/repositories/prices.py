"""SQL for model_prices."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ModelPrice


async def get_effective(
    session: AsyncSession, provider: str, model: str, at: datetime
) -> ModelPrice | None:
    """The price row valid at `at`: effective_from <= at < effective_to (or open-ended)."""
    stmt = (
        select(ModelPrice)
        .where(
            ModelPrice.provider == provider,
            ModelPrice.model == model,
            ModelPrice.effective_from <= at,
            or_(ModelPrice.effective_to.is_(None), ModelPrice.effective_to > at),
        )
        .order_by(ModelPrice.effective_from.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_current(session: AsyncSession, provider: str, model: str) -> ModelPrice | None:
    stmt = select(ModelPrice).where(
        ModelPrice.provider == provider,
        ModelPrice.model == model,
        ModelPrice.effective_to.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def add_price(
    session: AsyncSession,
    *,
    provider: str,
    model: str,
    input_per_m: Decimal,
    cached_input_per_m: Decimal,
    output_per_m: Decimal,
    effective_from: datetime,
    source_url: str | None,
) -> ModelPrice:
    """Insert a new price and close the currently open row for the same model."""
    await session.execute(
        update(ModelPrice)
        .where(
            ModelPrice.provider == provider,
            ModelPrice.model == model,
            ModelPrice.effective_to.is_(None),
            ModelPrice.effective_from < effective_from,
        )
        .values(effective_to=effective_from)
    )
    row = ModelPrice(
        provider=provider,
        model=model,
        input_per_m=input_per_m,
        cached_input_per_m=cached_input_per_m,
        output_per_m=output_per_m,
        currency="USD",
        effective_from=effective_from,
        source_url=source_url,
    )
    session.add(row)
    await session.flush()
    return row


async def list_prices(session: AsyncSession) -> list[ModelPrice]:
    stmt = select(ModelPrice).order_by(
        ModelPrice.provider, ModelPrice.model, ModelPrice.effective_from
    )
    return list((await session.execute(stmt)).scalars())
