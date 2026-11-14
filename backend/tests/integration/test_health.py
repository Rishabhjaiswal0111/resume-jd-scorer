"""HTTP-level tests for health probes, request ids and the error shape.

These use in-memory fakes for dependencies, so they run without Docker.
Tests marked `integration` hit the real Postgres from `make up`.
"""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.health import get_readiness_checks


async def _ok() -> None:
    return None


async def _boom() -> None:
    raise ConnectionError("db down")


async def test_healthz_ok(client: AsyncClient) -> None:
    res = await client.get("/api/v1/healthz")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["env"] == "test"


async def test_response_has_generated_request_id(client: AsyncClient) -> None:
    res = await client.get("/api/v1/healthz")
    assert len(res.headers["x-request-id"]) == 32


async def test_incoming_request_id_is_echoed(client: AsyncClient) -> None:
    res = await client.get("/api/v1/healthz", headers={"x-request-id": "trace-me-123"})
    assert res.headers["x-request-id"] == "trace-me-123"


async def test_readyz_ok_when_all_checks_pass(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_readiness_checks] = lambda: {"database": _ok, "storage": _ok}
    res = await client.get("/api/v1/readyz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "checks": {"database": "ok", "storage": "ok"}}


async def test_readyz_503_when_a_check_fails(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_readiness_checks] = lambda: {"database": _boom, "storage": _ok}
    res = await client.get("/api/v1/readyz")
    assert res.status_code == 503
    assert res.json()["checks"] == {"database": "fail", "storage": "ok"}


async def test_unknown_route_uses_error_shape(client: AsyncClient) -> None:
    res = await client.get("/api/v1/does-not-exist")
    assert res.status_code == 404
    error = res.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"] == res.headers["x-request-id"]


@pytest.mark.integration
async def test_readyz_against_real_database(client: AsyncClient) -> None:
    """Requires `make up` + `make migrate`. Skipped automatically if Postgres is down."""
    res = await client.get("/api/v1/readyz")
    if res.json()["checks"]["database"] == "fail":
        pytest.skip("Postgres not running (make up)")
    assert res.status_code == 200
