"""Accounts and sign-in sessions."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import InvalidCredentialsError
from app.core.logging import get_logger
from app.core.security import hash_password, new_session_token, token_hash, verify_password
from app.db.models import User, UserSession

log = get_logger(__name__)

# Verified against when the email is unknown, so a wrong email and a wrong password take
# the same time (no account enumeration by timing).
_DUMMY_HASH = hash_password("not-a-real-password")


@dataclass(frozen=True)
class NewSession:
    user: User
    token: str
    expires_at: datetime


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email.strip().lower())
    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert_user(
    session: AsyncSession, *, email: str, name: str, password: str, is_demo: bool = False
) -> User:
    """Create the user, or reset its name and password if it exists. Commits."""
    user = await get_user_by_email(session, email)
    if user is None:
        user = User(email=email.strip().lower(), name=name, is_demo=is_demo, password_hash="")
        session.add(user)
    user.name, user.is_demo = name, is_demo
    user.password_hash = hash_password(password)
    await session.commit()
    return user


async def login(
    session: AsyncSession, settings: Settings, *, email: str, password: str
) -> NewSession:
    user = await get_user_by_email(session, email)
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise InvalidCredentialsError("Email or password is incorrect")
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Email or password is incorrect")
    token = new_session_token()
    expires_at = datetime.now(UTC) + timedelta(days=settings.session_days)
    session.add(UserSession(user_id=user.id, token_hash=token_hash(token), expires_at=expires_at))
    await session.commit()
    log.info("login", user_id=str(user.id))
    return NewSession(user=user, token=token, expires_at=expires_at)


async def user_for_token(session: AsyncSession, token: str) -> User | None:
    stmt = (
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == token_hash(token),
            UserSession.expires_at > datetime.now(UTC),
        )
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    await session.commit()  # end the read: the request may go on to slow work
    return user


async def logout(session: AsyncSession, token: str) -> None:
    await session.execute(delete(UserSession).where(UserSession.token_hash == token_hash(token)))
    await session.commit()
