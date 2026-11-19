"""Concurrency regressions found by the stress test (eval/stress/REPORT.md, ADR-0007).

1. A request must not hold a pooled DB connection while the LLM parses a JD: with a tiny
   pool, a few concurrent first-time JDs used to time out waiting for a connection.
2. Concurrent requests for the same new JD must parse it once and share the rubric
   (they used to fail with a unique-constraint error on rubrics).
"""

import asyncio
import json
from pathlib import Path

import httpx2
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import LLMCall, Rubric
from app.llm.client import LLMClient
from app.services.scoring_service import PdfInput, ScoringService
from tests.conftest import DbContext
from tests.fakes import HAIKU, claude_message, seed_haiku_price

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parents[1] / "fixtures"
RUBRIC = json.loads((FIXTURES / "llm" / "synthetic_jd_backend.rubric.json").read_text())
EVALUATION = json.loads((FIXTURES / "llm" / "synthetic_resume_single.evaluation.json").read_text())
JD_TEXT = (
    "Senior Backend Engineer (Python). Build and run REST APIs in Python with PostgreSQL. "
    "Requirements: 6+ years backend engineering, Python, PostgreSQL, AWS, automated testing. "
    "Nice to have: Kafka, Kubernetes. Hybrid in London. " * 2
)


def slow_claude(latency_s: float) -> httpx2.MockTransport:
    """Answers JD parses with RUBRIC and evaluations with EVALUATION after `latency_s`."""

    async def handler(request: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(latency_s)
        body = json.loads(request.content)
        is_parse = "<job_description>" in body["messages"][0]["content"]
        return httpx2.Response(200, json=claude_message(RUBRIC if is_parse else EVALUATION))

    return httpx2.MockTransport(handler)


def resume() -> PdfInput:
    return PdfInput("cv.pdf", (FIXTURES / "pdfs" / "resume_single.pdf").read_bytes())


async def test_new_jds_do_not_starve_a_small_pool(db: DbContext) -> None:
    await seed_haiku_price(db.sessionmaker)
    db.settings.anthropic_api_key = SecretStr("k")
    # 2 connections in total, 3 concurrent first-time JDs, each parse takes 0.3 s.
    engine = create_async_engine(
        db.settings.database_url, pool_size=1, max_overflow=1, pool_timeout=3
    )
    try:
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        client = LLMClient(
            db.settings, sessionmaker, db.storage, anthropic_transport=slow_claude(0.3)
        )
        service = ScoringService(db.settings, sessionmaker, db.storage, client)
        runs = await asyncio.gather(
            *(service.score_pdfs(f"{JD_TEXT} Ref {i}", resume(), model=HAIKU) for i in range(3))
        )
        assert [r.status for r in runs] == ["completed"] * 3
    finally:
        await engine.dispose()


async def test_same_new_jd_is_parsed_once_and_shared(db: DbContext) -> None:
    await seed_haiku_price(db.sessionmaker)
    db.settings.anthropic_api_key = SecretStr("k")
    client = LLMClient(
        db.settings, db.sessionmaker, db.storage, anthropic_transport=slow_claude(0.2)
    )
    service = ScoringService(db.settings, db.sessionmaker, db.storage, client)

    runs = await asyncio.gather(
        *(service.score_pdfs(JD_TEXT, resume(), model=HAIKU) for _ in range(5))
    )

    assert [r.status for r in runs] == ["completed"] * 5
    assert len({r.rubric_id for r in runs}) == 1
    async with db.sessionmaker() as session:
        rubrics = (await session.execute(select(func.count()).select_from(Rubric))).scalar_one()
        parses = (
            await session.execute(
                select(func.count()).select_from(LLMCall).where(LLMCall.purpose == "jd_parse")
            )
        ).scalar_one()
    assert rubrics == 1
    assert parses == 1  # one paid parse, not five
