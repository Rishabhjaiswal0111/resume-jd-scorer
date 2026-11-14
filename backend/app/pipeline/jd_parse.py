"""JD text -> validated rubric (LLM call #1, PLAN.md 1.9)."""

import json
from dataclasses import dataclass, field
from uuid import UUID

from app.core.errors import LLMInvalidOutputError, RubricEmptyError
from app.core.logging import get_logger
from app.llm.client import LLMClient, LLMResult
from app.llm.prompts import load_prompt, render
from app.schemas.rubric import Criterion, RubricOutput

log = get_logger(__name__)

PROMPT_VERSION = "jd_parse.v1"


@dataclass
class ParsedRubric:
    rubric: RubricOutput
    prompt_version: str
    call_ids: list[UUID] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _dedupe_keys(criteria: list[Criterion]) -> tuple[list[Criterion], list[str]]:
    seen: dict[str, int] = {}
    out: list[Criterion] = []
    renamed: list[str] = []
    for criterion in criteria:
        key = criterion.key
        if key in seen:
            seen[key] += 1
            new_key = f"{key[:56]}_{seen[key]}"
            renamed.append(f"{key}->{new_key}")
            criterion = criterion.model_copy(update={"key": new_key})
        else:
            seen[key] = 1
        out.append(criterion)
    return out, renamed


async def parse_jd(client: LLMClient, jd_text: str, *, model: str | None = None) -> ParsedRubric:
    prompt = load_prompt(PROMPT_VERSION)
    messages = [
        {"role": "system", "content": prompt.system},
        {"role": "user", "content": render(prompt.user, {"jd_text": jd_text})},
    ]
    call_ids: list[UUID] = []
    result: LLMResult[RubricOutput]
    try:
        result = await client.complete_json(
            purpose="jd_parse",
            prompt_version=PROMPT_VERSION,
            messages=messages,
            output_model=RubricOutput,
            schema_name="rubric",
            model=model,
        )
    except LLMInvalidOutputError as error:
        call_ids.append(UUID(error.details["call_id"]))
        if prompt.repair is None:
            raise RuntimeError(f"{PROMPT_VERSION} has no '## repair' section") from error
        log.warning("jd_parse_repair", errors=error.details.get("errors", "")[:300])
        result = await client.complete_json(
            purpose="repair",
            prompt_version=PROMPT_VERSION,
            messages=[
                *messages,
                {"role": "assistant", "content": error.raw_text or ""},
                {
                    "role": "user",
                    "content": render(
                        prompt.repair, {"errors": str(error.details.get("errors", ""))[:1500]}
                    ),
                },
            ],
            output_model=RubricOutput,
            schema_name="rubric",
            model=model,
        )
    call_ids.append(result.call_id)

    rubric = result.value
    if not rubric.criteria:
        raise RubricEmptyError("No criteria found in the job description")
    criteria, renamed = _dedupe_keys(rubric.criteria)
    warnings = [f"duplicate_criterion_keys_renamed: {json.dumps(renamed)}"] if renamed else []
    if renamed:
        log.warning("jd_parse_duplicate_keys", renamed=renamed)
    return ParsedRubric(
        rubric=rubric.model_copy(update={"criteria": criteria}),
        prompt_version=PROMPT_VERSION,
        call_ids=call_ids,
        warnings=warnings,
    )
