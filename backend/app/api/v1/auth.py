"""Sign in / out and the current user."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import DemoInfo, LoginRequest, UserView
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _view(user: User) -> UserView:
    return UserView(id=user.id, email=user.email, name=user.name, is_demo=user.is_demo)


@router.post("/login", response_model=UserView)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UserView:
    new = await auth_service.login(session, settings, email=body.email, password=body.password)
    response.set_cookie(
        settings.session_cookie_name,
        new.token,
        max_age=settings.session_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.app_env in ("staging", "prod"),
        path="/",
    )
    return _view(new.user)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await auth_service.logout(session, token)
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserView)
async def me(user: User = Depends(current_user)) -> UserView:
    return _view(user)


@router.get("/demo", response_model=DemoInfo)
async def demo(settings: Settings = Depends(get_settings)) -> DemoInfo:
    if settings.is_prod:
        raise NotFoundError("No demo account here")
    return DemoInfo(email=settings.demo_email, password=settings.demo_password.get_secret_value())
