"""End-to-end: real PDFs -> extract -> PII strip -> rubric -> evaluate -> score -> ledger.

The LLM is the scripted fake; everything else (Postgres, storage, math) is real.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.errors import PdfScannedError
from app.db.models import CriterionEvaluation, LLMCall, ScoringRun
from app.llm.client import LLMClient
from app.services.scoring_service import PdfInput, ScoringService
from tests.conftest import DbContext
from tests.fakes import MODEL, FakeOpenRouter, completion, seed_price

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parents[1] / "fixtures"
RUBRIC = json.loads((FIXTURES / "llm" / "synthetic_jd_backend.rubric.json").read_text())
EVALUATION = json.loads((FIXTURES / "llm" / "synthetic_resume_single.evaluation.json").read_text())


def pdf(name: str) -> PdfInput:
    return PdfInput(name, (FIXTURES / "pdfs" / name).read_bytes())


def service(db: DbContext, fake: FakeOpenRouter) -> ScoringService:
    client = LLMClient(db.settings, db.sessionmaker, db.storage, transport=fake.transport)
    return ScoringService(db.settings, db.sessionmaker, db.storage, client)


async def test_score_replay_and_cost_invariant(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    fake = (
        FakeOpenRouter()
        .add("rubric", completion(RUBRIC, prompt_tokens=1200, completion_tokens=600))
        .add("evaluation", completion(EVALUATION, prompt_tokens=2000, completion_tokens=800))
    )
    svc = service(db, fake)
    run = await svc.score_pdfs(pdf("jd_backend.pdf"), pdf("resume_single.pdf"), model=MODEL)

    # Hand-computed (docs/scoring-spec.md): must_have 45 over factors 1,2,2,1,1 ->
    # 6.43 / 12.85 (drift) / 12.86 / 6.43 / 6.43; c_written_english forced Fail (normal, no
    # penalty). nice_to_have 5 -> 1.66 / 1.67 / 1.67 (open source Fail). must_avoid 10.
    # preferred empty -> forfeit 20. earned 38.57 + 3.33 + 10 + 10 + 10 = 71.90 / 80 = 89.875
    assert run.status == "completed"
    assert run.score == Decimal("90")

    async with db.sessionmaker() as session:
        rows = {
            r.criterion_key: r
            for r in (
                await session.execute(
                    select(CriterionEvaluation).where(CriterionEvaluation.run_id == run.id)
                )
            ).scalars()
        }
        ledger_sum = (
            await session.execute(
                select(func.sum(LLMCall.cost_usd)).where(LLMCall.run_id == run.id)
            )
        ).scalar_one()
    assert len(rows) == 9
    assert rows["c_written_english"].was_forced_fail
    assert rows["c_python_apis"].weight == Decimal("12.85")

    # Cost invariant: run cost == sum of its ledger rows. Evaluate call:
    # (2000 * 0.0507 + 800 * 0.2028) / 1e6 = 0.00026364. JD parse is the rubric's cost:
    # (1200 * 0.0507 + 600 * 0.2028) / 1e6 = 0.00018252.
    assert run.llm_cost_usd == ledger_sum == Decimal("0.00026364")
    assert run.rubric_cost_share_usd == Decimal("0.00018252")

    # PII never reaches the evaluate prompt.
    [evaluate_request] = fake.calls_for("evaluation")
    prompt = evaluate_request["messages"][1]["content"]
    assert "Jordan" not in prompt and "jordan.avery@example.com" not in prompt
    assert "<resume>\n[CANDIDATE]\n[EMAIL]" in prompt

    # Replay: identical score and breakdown, no LLM call, no cost.
    replay = await svc.replay(run.id)
    assert replay.score == run.score
    assert replay.breakdown == run.breakdown
    assert replay.llm_cost_usd == 0 and replay.replay_of_run_id == run.id
    assert len(fake.requests) == 2

    # Same JD again: rubric reused, JD parsed once; share is split across 2 runs.
    fake.add("evaluation", completion(EVALUATION))
    second = await svc.score_pdfs(pdf("jd_backend.pdf"), pdf("resume_single.pdf"), model=MODEL)
    assert len(fake.calls_for("rubric")) == 1
    assert second.rubric_id == run.rubric_id
    assert second.rubric_cost_share_usd == Decimal("0.00009126")


async def test_scanned_resume_fails_the_run(db: DbContext) -> None:
    await seed_price(db.sessionmaker)
    with pytest.raises(PdfScannedError):
        await service(db, FakeOpenRouter()).score_pdfs(
            pdf("jd_backend.pdf"), pdf("scanned_resume.pdf"), model=MODEL
        )
    async with db.sessionmaker() as session:
        run = (await session.execute(select(ScoringRun))).scalar_one()
    assert (run.status, run.error_code) == ("failed", "PDF_SCANNED")
