"""Command line entry point (PLAN.md 1.14).

uv run python -m app.cli score JD.pdf RESUME.pdf [--model openrouter/...] [--json]
uv run python -m app.cli replay RUN_ID
uv run python -m app.cli prices sync [--model openrouter/...]
uv run python -m app.cli prices list
"""

import argparse
import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.db.models import ScoringRun
from app.db.session import dispose_engine, get_sessionmaker
from app.llm.client import LLMClient
from app.llm.pricing import split_model_id
from app.repositories import llm_calls as calls_repo
from app.repositories import prices as prices_repo
from app.repositories import rubrics as rubrics_repo
from app.services import price_service
from app.services.scoring_service import PdfInput, ScoringService
from app.storage import get_storage


def _money(value: Decimal | None) -> str | None:
    """Plain decimal string (no exponent), e.g. 0.00026364, 0."""
    if value is None:
        return None
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _service(settings: Settings) -> ScoringService:
    sessionmaker = get_sessionmaker()
    storage = get_storage()
    return ScoringService(
        settings, sessionmaker, storage, LLMClient(settings, sessionmaker, storage)
    )


async def _run_summary(run: ScoringRun) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        calls = await calls_repo.list_for_run(session, run.id)
        rubric = await rubrics_repo.get(session, run.rubric_id) if run.rubric_id else None
    reported = [
        c.provider_reported_cost_usd for c in calls if c.provider_reported_cost_usd is not None
    ]
    provider_total = sum(reported, Decimal(0)) if reported else None
    return {
        "run_id": str(run.id),
        "status": run.status,
        "score": str(run.score),
        "role": rubric.title if rubric else None,
        "model": run.model,
        "engine_version": run.engine_version,
        "replay_of_run_id": str(run.replay_of_run_id) if run.replay_of_run_id else None,
        "pros": run.pros,
        "cons": run.cons,
        "criteria": (run.breakdown or {}).get("criteria", []),
        "warnings": run.warnings,
        "cost": {
            "run_llm_cost_usd": _money(run.llm_cost_usd),
            "run_provider_reported_usd": _money(provider_total),
            "rubric_cost_share_usd": _money(run.rubric_cost_share_usd),
            "calls": [
                {
                    "purpose": c.purpose,
                    "status": c.status,
                    "cache_hit": c.cache_hit,
                    "input_tokens": c.input_tokens,
                    "output_tokens": c.output_tokens,
                    "cost_usd": _money(c.cost_usd),
                    "provider_reported_cost_usd": _money(c.provider_reported_cost_usd),
                }
                for c in calls
            ],
        },
        "latency_ms": run.latency_ms,
    }


def _print_summary(summary: dict[str, Any]) -> None:
    print(f"\nScore: {summary['score']} / 100   ({summary['role']})")
    print(f"Run:   {summary['run_id']}   model={summary['model']}")
    print(f"Engine: {summary['engine_version']}")
    if summary["replay_of_run_id"]:
        print(f"Replay of: {summary['replay_of_run_id']}")
    print("\nPros:")
    for p in summary["pros"] or []:
        print(f"  + [{p['source']}] {p['text']}")
    print("\nCons:")
    for c in summary["cons"] or []:
        print(f"  - [{c['source']}] {c['text']}")
    print("\nCriteria:")
    for c in summary["criteria"]:
        forced = f"  (forced: {c['forced']})" if c["forced"] else ""
        print(
            f"  {c['key']:<32} {c['operator']:<13} {c['importance']:<7} "
            f"{c['outcome']:<13} {c['earned']:>6}/{c['weight']:<6}{forced}"
        )
    if summary["warnings"]:
        print("\nWarnings:", *summary["warnings"], sep="\n  ")
    cost = summary["cost"]
    reported = cost["run_provider_reported_usd"]
    reported_text = f"provider-reported ${reported}" if reported is not None else "no provider cost"
    print(
        f"\nCost: run ${cost['run_llm_cost_usd']} ({reported_text})"
        f"  + JD-parse share ${cost['rubric_cost_share_usd']}"
    )


async def _score(args: argparse.Namespace) -> int:
    settings = get_settings()
    jd, resume = Path(args.jd), Path(args.resume)
    run = await _service(settings).score_pdfs(
        PdfInput(jd.name, await asyncio.to_thread(jd.read_bytes)),
        PdfInput(resume.name, await asyncio.to_thread(resume.read_bytes)),
        model=args.model,
    )
    summary = await _run_summary(run)
    print(json.dumps(summary, indent=2)) if args.json else _print_summary(summary)
    return 0


async def _replay(args: argparse.Namespace) -> int:
    run = await _service(get_settings()).replay(UUID(args.run_id))
    summary = await _run_summary(run)
    print(json.dumps(summary, indent=2)) if args.json else _print_summary(summary)
    return 0


async def _prices_sync(args: argparse.Namespace) -> int:
    settings = get_settings()
    model = args.model or settings.llm_default_model
    provider, provider_model = split_model_id(model)
    if provider == "anthropic":
        published = price_service.anthropic_price(provider_model)
    elif provider == "openrouter":
        published = await price_service.fetch_openrouter_price(settings, provider_model)
    else:
        print(f"No price source for provider {provider!r}")
        return 2
    async with get_sessionmaker()() as session:
        result = await price_service.upsert_price(session, published)
        await session.commit()
    state = "added" if result.changed else "unchanged"
    print(
        f"{provider}/{provider_model}: in ${published.input_per_m}/M  "
        f"cached ${published.cached_input_per_m}/M  out ${published.output_per_m}/M  [{state}]"
    )
    return 0


async def _prices_list(_: argparse.Namespace) -> int:
    async with get_sessionmaker()() as session:
        rows = await prices_repo.list_prices(session)
    for r in rows:
        print(
            f"{r.provider}/{r.model}  in={r.input_per_m} cached={r.cached_input_per_m} "
            f"out={r.output_per_m}  from={r.effective_from:%Y-%m-%d %H:%M} "
            f"to={r.effective_to or '-'}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="JD x Resume scorer")
    sub = parser.add_subparsers(dest="command", required=True)

    score = sub.add_parser("score", help="score a resume PDF against a JD PDF")
    score.add_argument("jd")
    score.add_argument("resume")
    score.add_argument("--model", default=None)
    score.add_argument("--json", action="store_true")
    score.set_defaults(handler=_score)

    replay = sub.add_parser("replay", help="recompute a run's score without calling the LLM")
    replay.add_argument("run_id")
    replay.add_argument("--json", action="store_true")
    replay.set_defaults(handler=_replay)

    prices = sub.add_parser("prices", help="model price table")
    prices_sub = prices.add_subparsers(dest="prices_command", required=True)
    sync = prices_sub.add_parser("sync", help="fetch the current OpenRouter price for a model")
    sync.add_argument("--model", default=None)
    sync.set_defaults(handler=_prices_sync)
    prices_sub.add_parser("list").set_defaults(handler=_prices_list)
    return parser


async def _main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    try:
        code: int = await args.handler(args)
        return code
    except AppError as error:
        print(f"\nError {error.code}: {error.message}", file=sys.stderr)
        if error.details:
            print(json.dumps(error.details, indent=2, default=str), file=sys.stderr)
        return 1
    finally:
        await dispose_engine()


def main() -> None:
    sys.exit(asyncio.run(_main(sys.argv[1:])))


if __name__ == "__main__":
    main()
