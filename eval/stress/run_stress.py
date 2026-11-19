"""Stress-test the scoring pipeline on the generated corpus (eval/stress/samples).

    cd backend
    uv run python ../eval/stress/run_stress.py --label r1                       # fresh rubrics
    uv run python ../eval/stress/run_stress.py --label r4 --rubrics-from r1     # reuse r1's rubrics
    uv run python ../eval/stress/run_stress.py --label offline --fake-llm       # no API, $0

Isolation: uses its own database (`<db>_stress`, created + migrated on first use) and
storage root (backend/var/stress_storage), so the app's History is never touched.
The LLM response cache is OFF, so every run makes fresh model calls.

Each run: ingest all JDs/resumes (deduplicated) -> one rubric per JD (fresh, or reused
from an earlier run) -> score every pair from the manifest in a run-specific shuffled
order through ScoringService.score_documents -> replay every completed run (no LLM) to
check the engine is deterministic. Results: eval/stress/results/<label>/.
"""

import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "backend"
SAMPLES = HERE / "samples"
RESULTS = HERE / "results"
DEFAULT_MODEL = "anthropic/claude-haiku-5-5"


def _configure_env(fake: bool) -> str:
    """Point the app at the stress DB/storage BEFORE app settings are first read."""
    sys.path.insert(0, str(BACKEND))
    from app.core.config import Settings

    base = Settings().database_url
    parts = urlsplit(base)
    stress_db = parts.path.lstrip("/") + "_stress"
    os.environ["DATABASE_URL"] = urlunsplit(parts._replace(path="/" + stress_db))
    os.environ["STORAGE_LOCAL_ROOT"] = str(BACKEND / "var" / "stress_storage")
    os.environ["LLM_CACHE_ENABLED"] = "false"
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    os.environ.setdefault("DB_POOL_SIZE", "20")
    os.environ["MANUAL_LLM_DIR"] = str(BACKEND / "var" / "stress_manual_llm")
    if fake:
        os.environ["ANTHROPIC_API_KEY"] = "offline-fake"  # noqa: S105 - never sent anywhere
    return base


async def _ensure_database(base_url: str) -> None:
    import asyncpg

    parts = urlsplit(base_url.replace("postgresql+asyncpg", "postgresql"))
    target = parts.path.lstrip("/") + "_stress"
    conn = await asyncpg.connect(urlunsplit(parts._replace(path="/postgres")))
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", target)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{target}"')
            print(f"created database {target}")
    finally:
        await conn.close()
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], cwd=BACKEND, check=True,
                   env=os.environ.copy(), capture_output=True)


async def _ensure_price(model: str) -> None:
    from app.db.session import get_sessionmaker
    from app.llm.pricing import split_model_id
    from app.services import price_service

    provider, provider_model = split_model_id(model)
    if provider != "anthropic":
        return  # manual/<name> calls are recorded at $0 and need no price
    async with get_sessionmaker()() as session:
        await price_service.upsert_price(session, price_service.anthropic_price(provider_model))
        await session.commit()


async def _ingest(manifest: dict[str, Any]) -> tuple[dict[str, UUID], dict[str, str]]:
    from app.core.config import get_settings
    from app.db.session import get_sessionmaker
    from app.services.document_service import ingest_pdf, ingest_text
    from app.storage import get_storage

    settings, storage = get_settings(), get_storage()
    ids: dict[str, UUID] = {}
    errors: dict[str, str] = {}
    async with get_sessionmaker()() as session:
        for doc in manifest["jds"] + manifest["resumes"]:
            kind = "jd" if doc["id"].startswith("jd_") else "resume"
            path = SAMPLES / doc["path"]
            try:
                if path.suffix == ".txt":
                    stored = await ingest_text(session, storage, kind=kind,
                                               text=path.read_text(encoding="utf-8"))
                else:
                    stored = await ingest_pdf(session, storage, settings, kind=kind,
                                              filename=path.name, data=path.read_bytes())
                ids[doc["id"]] = stored.id
            except Exception as error:  # recorded, the run continues
                await session.rollback()
                errors[doc["id"]] = f"{type(error).__name__}: {error}"
    return ids, errors


async def _fresh_rubrics(manifest: dict[str, Any], doc_ids: dict[str, UUID], client: Any, model: str,
                         label: str, concurrency: int) -> tuple[dict[str, str], dict[str, str]]:
    from app.db.models import Rubric
    from app.db.session import get_sessionmaker
    from app.pipeline import jd_parse
    from app.repositories import documents as documents_repo
    from app.repositories import llm_calls as calls_repo
    from app.repositories import rubrics as rubrics_repo
    from app.services.document_service import load_text
    from app.storage import get_storage

    storage = get_storage()
    sem = asyncio.Semaphore(concurrency)
    out: dict[str, str] = {}
    errors: dict[str, str] = {}
    lock = asyncio.Lock()  # next_version() + insert must not interleave per JD

    async def one(jd_id: str) -> None:
        async with sem:
            try:
                async with get_sessionmaker()() as session:
                    jd = await documents_repo.get(session, doc_ids[jd_id])
                    assert jd is not None
                    jd_text = await load_text(storage, jd)
                    await session.commit()  # same rule as the app: no connection held during the LLM call
                    parsed = await jd_parse.parse_jd(client, jd_text, model=model)
                    async with lock:
                        rubric = Rubric(
                            jd_document_id=jd.id,
                            version=await rubrics_repo.next_version(session, jd.id),
                            title=parsed.rubric.title,
                            core_requirement=parsed.rubric.core_requirement,
                            role_summary=parsed.rubric.role_summary,
                            criteria=[c.model_dump() for c in parsed.rubric.criteria],
                            prompt_version=parsed.prompt_version,
                            model=model,
                            llm_call_id=parsed.call_ids[-1],
                            created_by=f"stress:{label}",
                        )
                        await rubrics_repo.insert(session, rubric)
                        await calls_repo.attach_rubric(session, parsed.call_ids, rubric.id)
                        await session.commit()
                    out[jd_id] = str(rubric.id)
            except Exception as error:
                errors[jd_id] = f"{type(error).__name__}: {getattr(error, 'code', '')} {error}"[:500]

    jd_ids = [d["id"] for d in manifest["jds"] if d["id"] in doc_ids]
    await asyncio.gather(*(one(j) for j in jd_ids))
    return out, errors


async def _score(manifest: dict[str, Any], doc_ids: dict[str, UUID], rubric_ids: dict[str, str],
                 service: Any, model: str, label: str, concurrency: int,
                 limit: int | None) -> list[dict[str, Any]]:
    from app.core.errors import AppError
    from app.db.session import get_sessionmaker
    from app.repositories import llm_calls as calls_repo

    pairs = list(manifest["pairs"])
    random.Random(f"order:{label}").shuffle(pairs)  # each run sees a different order
    if limit:
        pairs = pairs[:limit]
    sem = asyncio.Semaphore(concurrency)
    rows: list[dict[str, Any]] = []
    done = 0
    started = time.perf_counter()

    async def one(pair: dict[str, Any]) -> None:
        nonlocal done
        row: dict[str, Any] = {**pair, "label": label}
        async with sem:
            t0 = time.perf_counter()
            try:
                if pair["jd"] not in rubric_ids or pair["resume"] not in doc_ids:
                    raise LookupError("missing rubric or resume (ingest/parse failed)")
                run = await service.score_documents(UUID(rubric_ids[pair["jd"]]),
                                                    doc_ids[pair["resume"]], model=model)
                bd = run.breakdown or {}
                async with get_sessionmaker()() as session:
                    calls = await calls_repo.list_for_run(session, run.id)
                row.update({
                    "status": "completed",
                    "run_id": str(run.id),
                    "score": int(run.score),
                    "verdict": bd.get("verdict"),
                    "raw_score": float(Decimal(bd.get("raw_score", "0"))),
                    "role_overlap": (run.evaluation or {}).get("role_overlap", {}).get("level"),
                    "core_requirement": (run.evaluation or {}).get("core_requirement", {}).get("level"),
                    "caps": bd.get("caps", {}),
                    "knockouts_failed": bd.get("knockouts_failed", []),
                    "screening": bd.get("screening", []),
                    "group_relief": bd.get("group_relief"),
                    "forfeited_weight": bd.get("forfeited_weight"),
                    "criteria": [
                        {k: c[k] for k in ("key", "operator", "importance", "evidence_strength",
                                           "llm_outcome", "outcome", "forced", "knockout", "weight")}
                        for c in bd.get("criteria", [])
                    ],
                    "candidate_values": {c["key"]: c.get("candidate_value", "")
                                         for c in (run.evaluation or {}).get("criteria", [])},
                    "warnings": run.warnings,
                    "pii": bd.get("pii_redactions", {}),
                    "cost_usd": float(run.llm_cost_usd or 0),
                    "llm_calls": len(calls),
                    "llm_attempts_failed": sum(1 for c in calls if c.status != "success"),
                    "tokens_in": sum(c.input_tokens or 0 for c in calls),
                    "tokens_out": sum(c.output_tokens or 0 for c in calls),
                    "latency_ms": run.latency_ms,
                })
            except AppError as error:
                row.update({"status": "failed", "error_code": error.code, "error": error.message[:300],
                            "run_id": error.details.get("run_id")})
            except Exception as error:
                row.update({"status": "failed", "error_code": type(error).__name__,
                            "error": str(error)[:300]})
            row["wall_ms"] = int((time.perf_counter() - t0) * 1000)
        rows.append(row)
        done += 1
        if done % 25 == 0 or done == len(pairs):
            ok = sum(1 for r in rows if r["status"] == "completed")
            print(f"  [{label}] {done}/{len(pairs)} scored ({ok} ok) "
                  f"{time.perf_counter() - started:.0f}s", flush=True)

    await asyncio.gather(*(one(p) for p in pairs))
    return rows


async def _replay_check(service: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Recompute every completed run from its stored evaluation: the score must not move."""
    mismatches = []
    checked = 0
    for row in rows:
        if row["status"] != "completed":
            continue
        replay = await service.replay(UUID(row["run_id"]))
        checked += 1
        if int(replay.score) != row["score"]:
            mismatches.append({"run_id": row["run_id"], "score": row["score"], "replay": int(replay.score)})
    return {"checked": checked, "mismatches": mismatches}


async def _rubric_summary(rubric_ids: dict[str, str]) -> dict[str, Any]:
    from app.db.session import get_sessionmaker
    from app.repositories import llm_calls as calls_repo
    from app.repositories import rubrics as rubrics_repo

    out: dict[str, Any] = {}
    async with get_sessionmaker()() as session:
        for jd_id, rid in rubric_ids.items():
            rubric = await rubrics_repo.get(session, UUID(rid))
            assert rubric is not None
            out[jd_id] = {
                "rubric_id": rid,
                "title": rubric.title,
                "core_requirement": rubric.core_requirement,
                "criteria": rubric.criteria,
                "cost_usd": float(await calls_repo.sum_cost_for_rubric(session, rubric.id)),
            }
    return out


async def main_async(args: argparse.Namespace) -> None:
    base_url = _configure_env(args.fake_llm)
    await _ensure_database(base_url)

    from app.core.config import get_settings
    from app.db.session import dispose_engine, get_sessionmaker
    from app.llm.client import LLMClient
    from app.services.scoring_service import ScoringService
    from app.storage import get_storage

    from app.core.logging import configure_logging

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    assert settings.database_url.endswith("_stress"), "refusing to run against the main database"
    assert not settings.llm_cache_enabled
    model = args.model
    await _ensure_price(model)

    transport = None
    if args.fake_llm:
        sys.path.insert(0, str(HERE))
        import fake_llm

        transport = fake_llm.transport()
    sessionmaker, storage = get_sessionmaker(), get_storage()
    client = LLMClient(settings, sessionmaker, storage, anthropic_transport=transport)
    service = ScoringService(settings, sessionmaker, storage, client)

    manifest = json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))
    if args.jds:  # subset: these JDs and their pairs only
        wanted = set(args.jds.split(","))
        manifest["jds"] = [d for d in manifest["jds"] if d["id"] in wanted]
        manifest["pairs"] = [p for p in manifest["pairs"] if p["jd"] in wanted]
    out_dir = RESULTS / args.label
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    doc_ids, ingest_errors = await _ingest(manifest)
    print(f"[{args.label}] ingested {len(doc_ids)} documents, {len(ingest_errors)} errors")

    rubric_errors: dict[str, str] = {}
    if args.rubrics_from:
        src = json.loads((RESULTS / args.rubrics_from / "rubrics.json").read_text())
        rubric_ids = {jd: v["rubric_id"] for jd, v in src.items()}
    else:
        rubric_ids, rubric_errors = await _fresh_rubrics(manifest, doc_ids, client, model, args.label,
                                                         args.concurrency)
    t_rubrics = time.perf_counter() - t0
    print(f"[{args.label}] {len(rubric_ids)} rubrics ({len(rubric_errors)} failed) in {t_rubrics:.0f}s")
    rubrics = await _rubric_summary(rubric_ids)
    (out_dir / "rubrics.json").write_text(json.dumps(rubrics, indent=1, ensure_ascii=False))

    rows = await _score(manifest, doc_ids, rubric_ids, service, model, args.label, args.concurrency,
                        args.limit)
    rows.sort(key=lambda r: r["pair_id"])
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    replay = await _replay_check(service, rows) if not args.no_replay else {"checked": 0, "mismatches": []}
    meta = {
        "label": args.label,
        "model": "offline-fake" if args.fake_llm else model,
        "effort": settings.llm_effort,
        "rubrics": f"reused from {args.rubrics_from}" if args.rubrics_from else "fresh",
        "concurrency": args.concurrency,
        "pairs": len(rows),
        "completed": sum(1 for r in rows if r["status"] == "completed"),
        "ingest_errors": ingest_errors,
        "rubric_errors": rubric_errors,
        "rubric_cost_usd": 0.0 if args.rubrics_from else sum(v["cost_usd"] for v in rubrics.values()),
        "scoring_cost_usd": sum(r.get("cost_usd", 0) for r in rows),
        "rubric_seconds": round(t_rubrics, 1),
        "total_seconds": round(time.perf_counter() - t0, 1),
        "replay": replay,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: v for k, v in meta.items() if k not in ("ingest_errors", "rubric_errors")},
                     indent=1))
    await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", required=True, help="run name, e.g. r1")
    parser.add_argument("--rubrics-from", help="reuse the rubrics of an earlier run label")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--limit", type=int, help="score only the first N pairs (pilot)")
    parser.add_argument("--jds", help="comma-separated JD ids to run (default: all)")
    parser.add_argument("--fake-llm", action="store_true", help="offline keyword stand-in for Claude")
    parser.add_argument("--no-replay", action="store_true")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
