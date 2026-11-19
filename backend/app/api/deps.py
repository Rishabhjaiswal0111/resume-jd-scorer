"""Shared request dependencies."""

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import UnauthenticatedError
from app.db.models import User
from app.db.session import get_session
from app.services import auth_service


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User:
    """The signed-in user, or 401 UNAUTHENTICATED."""
    token = request.cookies.get(settings.session_cookie_name)
    user = await auth_service.user_for_token(session, token) if token else None
    if user is None:
        raise UnauthenticatedError("Sign in to continue")
    return user
