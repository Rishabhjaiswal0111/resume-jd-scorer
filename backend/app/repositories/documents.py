"""SQL for documents."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document


async def get(session: AsyncSession, document_id: UUID) -> Document | None:
    return await session.get(Document, document_id)


async def get_by_hash(session: AsyncSession, kind: str, sha256: str) -> Document | None:
    stmt = select(Document).where(Document.kind == kind, Document.sha256 == sha256)
    return (await session.execute(stmt)).scalar_one_or_none()


async def insert(session: AsyncSession, document: Document) -> Document:
    session.add(document)
    await session.flush()
    return document
