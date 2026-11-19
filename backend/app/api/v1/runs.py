"""Scoring runs (read-only). Runs are created by the background worker for job candidates."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.core.errors import NotFoundError
from app.db.models import User
from app.db.session import get_session
from app.schemas.runs import RunDetail
from app.services import job_service
from app.services.run_view import run_detail

router = APIRouter(tags=["runs"])


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> RunDetail:
    """A run, if it belongs to one of your jobs."""
    if not await job_service.run_visible_to(session, user, run_id):
        raise NotFoundError(f"Run {run_id} not found")
    return await run_detail(session, run_id)
