import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path

import asyncpg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_engine, get_sessionmaker
from app.main import create_app
from app.storage import get_storage
from app.storage.base import Storage

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Test settings: isolated storage dir, test env. Caches are reset around each test."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()
    get_storage.cache_clear()
    yield get_settings()
    get_settings.cache_clear()
    get_storage.cache_clear()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------- database


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """A dedicated `<db>_test` database, created and migrated once per session.

    Skipped when Postgres is down locally; in CI (CI=true) a missing DB is a failure.
    """
    base = make_url(os.environ.get("DATABASE_URL") or Settings().database_url)
    name = f"{base.database}_test"
    test_url = base.set(database=name)

    async def ensure_database() -> None:
        conn = await asyncpg.connect(
            user=base.username,
            password=base.password,
            host=base.host,
            port=base.port,
            database=base.database,
            timeout=5,
        )
        try:
            if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name):
                await conn.execute(f'CREATE DATABASE "{name}"')
        finally:
            await conn.close()

    try:
        asyncio.run(ensure_database())
    except (OSError, asyncpg.PostgresError) as error:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"Postgres not reachable ({type(error).__name__}); run `make up`")

    rendered = test_url.render_as_string(hide_password=False)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": rendered},
        check=True,
        capture_output=True,
    )
    return rendered


@dataclass
class DbContext:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    storage: Storage


@pytest.fixture
async def db(
    test_database_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[DbContext]:
    """Real Postgres (test DB) + temp storage. All tables are truncated afterwards."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("LLM_RETRY_BASE_SECONDS", "0")
    monkeypatch.setenv("MANUAL_LLM_WAIT_SECONDS", "0")
    for cached in (get_settings, get_storage, get_engine, get_sessionmaker):
        cached.cache_clear()
    try:
        yield DbContext(get_settings(), get_sessionmaker(), get_storage())
    finally:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        async with get_engine().begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
        await get_engine().dispose()
        for cached in (get_settings, get_storage, get_engine, get_sessionmaker):
            cached.cache_clear()
