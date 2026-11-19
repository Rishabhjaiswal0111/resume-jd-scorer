"""HTTP: sign-in, jobs, candidates, background scoring and search, with a fake Claude."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.llm.client import LLMClient
from app.main import create_app
from app.services import auth_service
from app.services.worker import Worker
from tests.conftest import DbContext
from tests.fakes import HAIKU, FakeAnthropic, claude_message, seed_haiku_price

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parents[1] / "fixtures"
RUBRIC = json.loads((FIXTURES / "llm" / "synthetic_jd_backend.rubric.json").read_text())
EVALUATION = json.loads((FIXTURES / "llm" / "synthetic_resume_single.evaluation.json").read_text())

JD_TEXT = """Senior Backend Engineer (Python)
Acme Analytics - Remote (EU time zones)

•\tDesign and operate the APIs behind our analytics platform.
•\t5+ years of professional software engineering experience
•\t3+ years building production APIs in Python (FastAPI or Django)
•\tStrong PostgreSQL skills: schema design, query tuning, migrations
"""


def pdf(name: str) -> tuple[str, bytes, str]:
    return (name, (FIXTURES / "pdfs" / name).read_bytes(), "application/pdf")


class Env:
    def __init__(self, db: DbContext, fake: FakeAnthropic) -> None:
        self.db, self.fake = db, fake
        llm = LLMClient(
            db.settings, db.sessionmaker, db.storage, anthropic_transport=fake.transport
        )
        self.worker = Worker(db.settings, db.sessionmaker, db.storage, llm)


@pytest.fixture
async def env(db: DbContext) -> Env:
    db.settings.anthropic_api_key = SecretStr("k")
    db.settings.llm_default_model = HAIKU
    await seed_haiku_price(db.sessionmaker)
    async with db.sessionmaker() as session:
        for email in ("alice@example.com", "bob@example.com"):
            await auth_service.upsert_user(session, email=email, name=email[:3], password="pw-123")
    return Env(db, FakeAnthropic())


@asynccontextmanager
async def signed_in(db: DbContext, email: str = "alice@example.com") -> AsyncIterator[AsyncClient]:
    app = create_app(db.settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        res = await http.post("/api/v1/auth/login", json={"email": email, "password": "pw-123"})
        assert res.status_code == 200, res.text
        yield http


async def ok(res: Any, status: int = 200) -> Any:
    assert res.status_code == status, res.text
    return res.json() if res.content else None


# ---------------------------------------------------------------- auth


async def test_everything_needs_a_session(env: Env) -> None:
    app = create_app(env.db.settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        for path in ("/api/v1/jobs", "/api/v1/candidates", "/api/v1/auth/me"):
            res = await http.get(path)
            assert res.status_code == 401
            assert res.json()["error"]["code"] == "UNAUTHENTICATED"
        bad = await http.post(
            "/api/v1/auth/login", json={"email": "alice@example.com", "password": "nope"}
        )
        assert bad.status_code == 401 and bad.json()["error"]["code"] == "INVALID_CREDENTIALS"
        unknown = await http.post(
            "/api/v1/auth/login", json={"email": "who@example.com", "password": "nope"}
        )
        assert unknown.json()["error"]["message"] == bad.json()["error"]["message"]


async def test_login_me_logout(env: Env) -> None:
    async with signed_in(env.db) as http:
        me = await ok(await http.get("/api/v1/auth/me"))
        assert me["email"] == "alice@example.com"
        cookie = http.cookies.get(env.db.settings.session_cookie_name)
        assert cookie and len(cookie) > 30
        await ok(await http.post("/api/v1/auth/logout"), 204)
        # The server forgets the session, even if a client kept the cookie.
        http.cookies.set(env.db.settings.session_cookie_name, cookie)
        assert (await http.get("/api/v1/auth/me")).status_code == 401


# ---------------------------------------------------------------- jobs + scoring


async def test_job_with_candidates_is_parsed_and_scored_in_the_background(env: Env) -> None:
    env.fake.add(claude_message(RUBRIC), claude_message(EVALUATION))
    async with signed_in(env.db) as http:
        job = await ok(await http.post("/api/v1/jobs", files={"jd": pdf("jd_backend.pdf")}), 201)
        assert job["status"] == "pending" and job["title"] == "jd_backend"
        assert "Backend" in job["jd_text"]

        upload = await ok(
            await http.post(
                f"/api/v1/jobs/{job['id']}/candidates",
                files=[
                    ("resumes", pdf("resume_single.pdf")),
                    ("resumes", pdf("scanned_resume.pdf")),
                ],
            ),
            201,
        )
        # The scanned PDF is reported; the good one is queued.
        assert [e["code"] for e in upload["errors"]] == ["PDF_SCANNED"]
        assert [c["status"] for c in upload["added"]] == ["queued"]

        assert await env.worker.run_until_idle() == 2  # parse the JD, then score

        job = await ok(await http.get(f"/api/v1/jobs/{job['id']}"))
        assert job["status"] == "ready"
        assert job["title"] == "Senior Backend Engineer (Python)"
        assert job["counts"] == {
            "total": 1,
            "scored": 1,
            "in_progress": 0,
            "failed": 0,
            "strong": 1,
        }
        assert job["best_score"] == "90"
        assert {r["operator"] for r in job["requirements"]} >= {"must_have"}

        [item] = await ok(await http.get(f"/api/v1/jobs/{job['id']}/candidates"))
        assert item["status"] == "scored" and item["score"] == "90"
        assert item["verdict"] == "Strong fit" and item["summary"]
        detail = await ok(await http.get(f"/api/v1/jobs/{job['id']}/candidates/{item['id']}"))
        assert detail["run"]["score"] == "90" and detail["job_title"] == job["title"]
        await ok(await http.get(f"/api/v1/runs/{item['run_id']}"))

        listed = await ok(await http.get("/api/v1/jobs"))
        assert [j["id"] for j in listed] == [job["id"]]
        preview = await http.get(f"/api/v1/jobs/{job['id']}/document")
        assert preview.headers["content-type"] == "application/pdf"
        assert preview.headers["content-disposition"].startswith("inline")
        resume = await http.get(f"/api/v1/candidates/{item['candidate']['id']}/resume")
        assert resume.status_code == 200 and resume.content.startswith(b"%PDF")

    # Another account sees none of it.
    async with signed_in(env.db, "bob@example.com") as other:
        assert await ok(await other.get("/api/v1/jobs")) == []
        for path in (
            f"/api/v1/jobs/{job['id']}",
            f"/api/v1/jobs/{job['id']}/candidates",
            f"/api/v1/runs/{item['run_id']}",
            f"/api/v1/candidates/{item['candidate']['id']}/resume",
        ):
            assert (await other.get(path)).status_code == 404, path


async def test_same_pasted_jd_opens_the_existing_job(env: Env) -> None:
    async with signed_in(env.db) as http:
        first = await ok(await http.post("/api/v1/jobs", data={"jd_text": JD_TEXT}), 201)
        again = await ok(
            await http.post("/api/v1/jobs", data={"jd_text": JD_TEXT.replace("\t", "  ")}), 201
        )
        assert again["id"] == first["id"]
        assert first["title"] == "Senior Backend Engineer (Python)"  # first line until parsed
        assert first["source"] == "text"
        preview = await http.get(f"/api/v1/jobs/{first['id']}/document")
        assert preview.headers["content-type"].startswith("text/plain")


@pytest.mark.parametrize(
    ("data", "with_pdf"),
    [({}, False), ({"jd_text": JD_TEXT}, True), ({"jd_text": "   "}, False)],
    ids=["neither", "both", "blank-text"],
)
async def test_jd_must_be_exactly_one_of_pdf_or_text(
    env: Env, data: dict[str, str], with_pdf: bool
) -> None:
    async with signed_in(env.db) as http:
        files = {"jd": pdf("jd_backend.pdf")} if with_pdf else None
        res = await http.post("/api/v1/jobs", data=data, files=files)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_failed_parse_can_be_retried(env: Env) -> None:
    # The provider fails every attempt (retries exhausted): the job fails; Retry re-queues it.
    down = httpx.Response(500, json={"type": "error", "error": {"message": "overloaded"}})
    attempts = env.db.settings.llm_max_retries + 1
    env.fake.add(*([down] * attempts), claude_message(RUBRIC))
    async with signed_in(env.db) as http:
        job = await ok(await http.post("/api/v1/jobs", data={"jd_text": JD_TEXT}), 201)
        await env.worker.run_until_idle()
        failed = await ok(await http.get(f"/api/v1/jobs/{job['id']}"))
        assert failed["status"] == "failed" and failed["error_code"] == "LLM_PROVIDER_ERROR"
        await ok(await http.post(f"/api/v1/jobs/{job['id']}/retry"))
        await env.worker.run_until_idle()
        assert (await ok(await http.get(f"/api/v1/jobs/{job['id']}")))["status"] == "ready"


# ---------------------------------------------------------------- database + search


async def test_search_ranks_resumes_and_adds_them_to_a_job(env: Env) -> None:
    env.fake.add(claude_message(RUBRIC), claude_message(EVALUATION))
    async with signed_in(env.db) as http:
        uploaded = await ok(
            await http.post(
                "/api/v1/candidates",
                files=[
                    ("resumes", pdf("resume_single.pdf")),
                    ("resumes", pdf("resume_two_column.pdf")),
                    ("resumes", pdf("corrupt.pdf")),
                ],
            ),
            201,
        )
        assert len(uploaded["added"]) == 2
        assert [e["code"] for e in uploaded["errors"]] == ["PDF_UNREADABLE"]
        assert len(await ok(await http.get("/api/v1/candidates"))) == 2

        result = await ok(
            await http.get("/api/v1/candidates/search", params={"q": "Python PostgreSQL"})
        )
        assert result["total_candidates"] == 2
        assert result["terms"] == ["Python", "PostgreSQL"]
        top = result["hits"][0]
        assert top["match"] == 100 and all(t["matched"] for t in top["terms"])
        assert "\u0001" in top["snippet"]  # highlighted words
        assert top["jobs"] == []

        # Terms are matched per resume, not across the database: "Django" is only in the
        # single-column resume, "Kubernetes" only in the two-column one.
        split = await ok(
            await http.get("/api/v1/candidates/search", params={"q": "Django FastAPI Python"})
        )
        first, second = split["hits"]
        assert first["match"] == 100 and second["match"] < 50
        assert {t["term"]: t["matched"] for t in second["terms"]} == {
            "Django": False,
            "FastAPI": False,
            "Python": True,
        }
        k8s = await ok(await http.get("/api/v1/candidates/search", params={"q": "kubernetes"}))
        assert len(k8s["hits"]) == 1

        nothing = await ok(await http.get("/api/v1/candidates/search", params={"q": "the and"}))
        assert nothing["hits"] == [] and nothing["terms"] == []

        job = await ok(await http.post("/api/v1/jobs", data={"jd_text": JD_TEXT}), 201)
        added = await ok(
            await http.post(
                f"/api/v1/jobs/{job['id']}/candidates/existing",
                json={"candidate_ids": [top["candidate"]["id"]]},
            )
        )
        assert [(a["status"], a["source"]) for a in added] == [("queued", "search")]
        await env.worker.run_until_idle()
        again = await ok(await http.get("/api/v1/candidates/search", params={"q": "Python"}))
        hit = next(h for h in again["hits"] if h["candidate"]["id"] == top["candidate"]["id"])
        assert hit["jobs"][0]["job_id"] == job["id"] and hit["jobs"][0]["status"] == "scored"

    async with signed_in(env.db, "bob@example.com") as other:
        mine = await ok(await other.get("/api/v1/candidates/search", params={"q": "Python"}))
        assert mine["total_candidates"] == 0 and mine["hits"] == []
        stolen = await other.post(
            f"/api/v1/jobs/{job['id']}/candidates/existing",
            json={"candidate_ids": [top["candidate"]["id"]]},
        )
        assert stolen.status_code == 404


async def test_concurrent_workers_never_take_the_same_candidate(env: Env) -> None:
    resumes = ("resume_single.pdf", "resume_two_column.pdf", "resume_multipage.pdf")
    env.fake.add(claude_message(RUBRIC), *[claude_message(EVALUATION)] * len(resumes))
    async with signed_in(env.db) as http:
        job = await ok(await http.post("/api/v1/jobs", data={"jd_text": JD_TEXT}), 201)
        await env.worker.run_once()  # parse
        await ok(
            await http.post(
                f"/api/v1/jobs/{job['id']}/candidates",
                files=[("resumes", pdf(name)) for name in resumes],
            ),
            201,
        )
        llm = LLMClient(
            env.db.settings,
            env.db.sessionmaker,
            env.db.storage,
            anthropic_transport=env.fake.transport,
        )
        workers = [
            Worker(env.db.settings, env.db.sessionmaker, env.db.storage, llm) for _ in range(4)
        ]
        done = await asyncio.gather(*(w.run_once() for w in workers))
        assert sorted(done) == [False, True, True, True]
        items = await ok(await http.get(f"/api/v1/jobs/{job['id']}/candidates"))
        assert [i["status"] for i in items] == ["scored"] * 3
        assert len(env.fake.requests) == 1 + len(resumes)  # one evaluation each, no repeats


async def test_shutdown_mid_task_hands_the_claim_back(env: Env, tmp_path: Path) -> None:
    """A deploy / reload cancels workers mid-LLM-call; the row must not stay claimed."""
    env.db.settings.llm_default_model = "manual/test"
    env.db.settings.manual_llm_dir = tmp_path / "manual"
    env.db.settings.manual_llm_wait_seconds = 30  # blocks until cancelled
    async with signed_in(env.db) as http:
        job = await ok(await http.post("/api/v1/jobs", data={"jd_text": JD_TEXT}), 201)
        llm = LLMClient(env.db.settings, env.db.sessionmaker, env.db.storage)
        worker = Worker(env.db.settings, env.db.sessionmaker, env.db.storage, llm)
        task = asyncio.create_task(worker.run_once())
        for _ in range(50):  # until the prompt is written, i.e. it is waiting on the "LLM"
            if list((tmp_path / "manual").glob("*.request.md")):
                break
            await asyncio.sleep(0.05)
        assert (await ok(await http.get(f"/api/v1/jobs/{job['id']}")))["status"] == "parsing"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (await ok(await http.get(f"/api/v1/jobs/{job['id']}")))["status"] == "pending"
