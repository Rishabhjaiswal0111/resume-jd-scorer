"""Liveness and readiness probes.

- /healthz: the process is up (no dependencies touched).
- /readyz:  database and storage are reachable; 503 otherwise.
"""

from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app import __version__
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import ping_database
from app.storage import get_storage

router = APIRouter(tags=["health"])
log = get_logger(__name__)

CheckFn = Callable[[], Awaitable[None]]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    env: str


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, Literal["ok", "fail"]]


async def _storage_check() -> None:
    await get_storage().healthcheck()


def get_readiness_checks() -> dict[str, CheckFn]:
    """Overridable in tests via app.dependency_overrides."""
    return {"database": ping_database, "storage": _storage_check}


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, env=get_settings().app_env)


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def readyz(
    response: Response,
    checks: dict[str, CheckFn] = Depends(get_readiness_checks),
) -> ReadinessResponse:
    results: dict[str, Literal["ok", "fail"]] = {}
    for name, check in checks.items():
        try:
            await check()
            results[name] = "ok"
        except Exception as exc:
            log.warning("readiness_check_failed", check=name, error=str(exc))
            results[name] = "fail"

    healthy = all(value == "ok" for value in results.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ok" if healthy else "degraded", checks=results)
