"""JD document -> rubric, parsed once per (JD, prompt version, model) — PLAN.md principle 4."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Document, Rubric
from app.llm.client import LLMClient
from app.pipeline import jd_parse
from app.repositories import llm_calls as calls_repo
from app.repositories import rubrics as rubrics_repo
from app.services.document_service import load_text
from app.storage.base import Storage

log = get_logger(__name__)


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
    cached = await rubrics_repo.latest_for_jd(session, jd.id, jd_parse.PROMPT_VERSION, model)
    if cached is not None:
        log.info("rubric_cache_hit", rubric_id=str(cached.id), jd_document_id=str(jd.id))
        return RubricResult(rubric=cached, cached=True)

    parsed = await jd_parse.parse_jd(client, await load_text(storage, jd), model=model)
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
    )
    await rubrics_repo.insert(session, rubric)
    await calls_repo.attach_rubric(session, parsed.call_ids, rubric.id)
    await session.commit()
    log.info(
        "rubric_created",
        rubric_id=str(rubric.id),
        criteria=len(rubric.criteria),
        warnings=parsed.warnings,
    )
    return RubricResult(rubric=rubric, cached=False)
