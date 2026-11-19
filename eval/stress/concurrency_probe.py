"""Concurrency probe of the real API code path (ScoringService.score_pdfs) with the app's
DB pool settings, using the offline fake model with simulated latency.

    cd backend && uv run python ../eval/stress/concurrency_probe.py --latency 3 --levels 5,10,20,40

Every request uses a NEW pasted JD (unique nonce), so each one goes through JD parsing and
evaluation exactly like a first-time upload in the UI. Writes results/concurrency.json.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_stress  # noqa: E402  (reuses its env isolation + DB bootstrap)


async def main_async(args: argparse.Namespace) -> None:
    os.environ.pop("DB_POOL_SIZE", None)  # the app's own default pool
    base = run_stress._configure_env(fake=True)
    os.environ.pop("DB_POOL_SIZE", None)
    await run_stress._ensure_database(base)
    import fake_llm
    from app.core.config import get_settings
    from app.core.errors import AppError
    from app.db.session import dispose_engine, get_sessionmaker
    from app.llm.client import LLMClient
    from app.services.scoring_service import PdfInput, ScoringService
    from app.storage import get_storage

    settings = get_settings()
    assert settings.database_url.endswith("_stress")
    await run_stress._ensure_price(run_stress.DEFAULT_MODEL)
    manifest = json.loads((run_stress.SAMPLES / "manifest.json").read_text())
    jd_text = (run_stress.SAMPLES / "jds" / "jd_001_backend_python_junior.txt").read_text()
    resume = next(r for r in manifest["resumes"] if r["id"] == "cv_003")
    pdf = PdfInput("cv.pdf", (run_stress.SAMPLES / resume["path"]).read_bytes())
    out = {"latency_s": args.latency, "db_pool_size": settings.db_pool_size, "levels": []}
    for level in [int(x) for x in args.levels.split(",")]:
        sm, storage = get_sessionmaker(), get_storage()
        client = LLMClient(settings, sm, storage, anthropic_transport=fake_llm.transport(args.latency))
        service = ScoringService(settings, sm, storage, client)
        nonce = time.time_ns()

        async def one(i: int) -> str:
            try:
                await service.score_pdfs(f"{jd_text}\nRef: {nonce}-{i}", pdf, model=run_stress.DEFAULT_MODEL)
                return "completed"
            except AppError as e:
                return e.code
            except Exception as e:  # noqa: BLE001
                return f"{type(e).__name__}: {str(e)[:80]}"

        t0 = time.perf_counter()
        results = await asyncio.gather(*(one(i) for i in range(level)))
        took = time.perf_counter() - t0
        counts = Counter(results)
        out["levels"].append({"concurrent_requests": level, "seconds": round(took, 1), "outcomes": dict(counts)})
        print(f"{level:>3} concurrent new-JD requests: {dict(counts)} in {took:.1f}s", flush=True)
    await dispose_engine()
    (run_stress.RESULTS / "concurrency.json").write_text(json.dumps(out, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latency", type=float, default=3.0, help="simulated seconds per model call")
    ap.add_argument("--levels", default="5,10,20,40")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
