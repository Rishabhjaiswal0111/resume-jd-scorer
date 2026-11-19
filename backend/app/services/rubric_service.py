"""JD document -> rubric, parsed once per (JD, prompt version, model) — PLAN.md principle 4.

Concurrency (ADR-0007, found by eval/stress):
- No pooled DB connection is held while the LLM parses the JD: the read transaction is
  committed first. Holding it starved the pool (15 concurrent new JDs -> all failed).
- One parse per JD per process: a per-JD asyncio lock makes concurrent requests for the
  same new JD wait for the first parse and reuse its rubric.
- Across processes the unique (jd_document_id, version) constraint is the backstop: a
  losing insert is rolled back to a savepoint and the winner's rubric is reused.
"""

import asyncio
import time
import weakref
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.timing import elapsed_ms
from app.db.models import Document, Rubric
from app.llm.client import LLMClient
from app.pipeline import jd_parse
from app.repositories import llm_calls as calls_repo
from app.repositories import rubrics as rubrics_repo
from app.services.document_service import load_text
from app.storage.base import Storage

log = get_logger(__name__)

# Entries disappear once no request holds or waits on the lock.
_jd_locks: "weakref.WeakValueDictionary[UUID, asyncio.Lock]" = weakref.WeakValueDictionary()
_INSERT_ATTEMPTS = 2


def _lock_for(jd_id: UUID) -> asyncio.Lock:
    lock = _jd_locks.get(jd_id)
    if lock is None:
        lock = asyncio.Lock()
        _jd_locks[jd_id] = lock
    return lock


@dataclass
class RubricResult:
    rubric: Rubric
    cached: bool


async def get_or_create_rubric(
    session: AsyncSession,
    storage: Storage,
    client: LLMClient,
    jd: Document,
    *,
    model: str,
) -> RubricResult:
    version = jd_parse.PROMPT_VERSION
    cached = await rubrics_repo.latest_for_jd(session, jd.id, version, model)
    await session.commit()  # end the read: no connection held while waiting or parsing
    if cached is not None:
        log.info("rubric_cache_hit", rubric_id=str(cached.id), jd_document_id=str(jd.id))
        return RubricResult(rubric=cached, cached=True)

    async with _lock_for(jd.id):
        # Another request may have built it while we waited for the lock.
        cached = await rubrics_repo.latest_for_jd(session, jd.id, version, model)
        await session.commit()
        if cached is not None:
            log.info("rubric_reused_after_wait", rubric_id=str(cached.id))
            return RubricResult(rubric=cached, cached=True)

        parse_started = time.perf_counter()
        parsed = await jd_parse.parse_jd(client, await load_text(storage, jd), model=model)
        parse_ms = elapsed_ms(parse_started)
        for attempt in range(1, _INSERT_ATTEMPTS + 1):
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
                created_by="llm",
                parse_ms=parse_ms,
            )
            try:
                async with session.begin_nested():  # savepoint: a lost race undoes only this
                    await rubrics_repo.insert(session, rubric)
            except IntegrityError:
                # Another process inserted this version first (same JD, same moment).
                winner = await rubrics_repo.latest_for_jd(session, jd.id, version, model)
                if winner is not None:
                    await session.commit()
                    log.info("rubric_insert_race_lost", rubric_id=str(winner.id))
                    return RubricResult(rubric=winner, cached=True)
                if attempt == _INSERT_ATTEMPTS:
                    raise
                continue
            await calls_repo.attach_rubric(session, parsed.call_ids, rubric.id)
            await session.commit()
            break
    log.info(
        "rubric_created",
        rubric_id=str(rubric.id),
        parse_ms=parse_ms,
        criteria=len(rubric.criteria),
        warnings=parsed.warnings,
    )
    return RubricResult(rubric=rubric, cached=False)
