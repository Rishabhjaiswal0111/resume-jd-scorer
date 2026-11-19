"""Resume x rubric -> validated per-criterion grades (LLM call #2, PLAN.md 1.10 / §7.2).

Validation (§7.2): every rubric key must appear exactly once.
- unknown keys: dropped (logged, warning)
- duplicate keys: first one kept (warning)
- missing keys: one repair call; still missing => Fail "Not evaluated" + run warning
- schema-invalid output: one repair call; still invalid => LLM_INVALID_OUTPUT
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from app.core.errors import LLMInvalidOutputError
from app.core.logging import get_logger
from app.llm.client import LLMClient, LLMResult, llm_json_schema
from app.llm.prompts import Prompt, load_prompt, render
from app.schemas.evaluation import CriterionResult, EvaluationOutput
from app.schemas.rubric import Criterion

log = get_logger(__name__)

PROMPT_VERSION = "evaluate.v3"  # v3: today's date in the prompt (ADR-0007)
NOT_EVALUATED = "Not evaluated"


@dataclass
class RubricView:
    title: str
    role_summary: str
    core_requirement: str
    criteria: list[Criterion]


@dataclass
class EvaluationResult:
    evaluation: EvaluationOutput  # complete: exactly one result per rubric key, rubric order
    prompt_version: str
    call_ids: list[UUID] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def evaluation_schema(keys: Sequence[str]) -> dict[str, Any]:
    """Strict schema with the criterion `key` restricted to this rubric's keys."""
    schema = llm_json_schema(EvaluationOutput)
    schema["properties"]["criteria"]["items"]["properties"]["key"]["enum"] = list(keys)
    return schema


def _criteria_json(criteria: Sequence[Criterion]) -> str:
    return json.dumps(
        [c.model_dump(exclude={"attribute"}) for c in criteria], ensure_ascii=False, indent=1
    )


def reconcile(
    output: EvaluationOutput, keys: Sequence[str]
) -> tuple[dict[str, CriterionResult], list[str], list[str], list[str]]:
    """-> (results by key, missing keys, unknown keys, duplicate keys)."""
    wanted = set(keys)
    by_key: dict[str, CriterionResult] = {}
    unknown: list[str] = []
    duplicates: list[str] = []
    for item in output.criteria:
        if item.key not in wanted:
            unknown.append(item.key)
        elif item.key in by_key:
            duplicates.append(item.key)
        else:
            by_key[item.key] = item
    missing = [k for k in keys if k not in by_key]
    return by_key, missing, unknown, duplicates


def _repair_messages(
    prompt: Prompt, messages: list[dict[str, str]], raw_text: str, errors: str
) -> list[dict[str, str]]:
    if prompt.repair is None:
        raise RuntimeError(f"{prompt.version} has no '## repair' section")
    return [
        *messages,
        {"role": "assistant", "content": raw_text},
        {"role": "user", "content": render(prompt.repair, {"errors": errors[:1500]})},
    ]


async def evaluate_resume(
    client: LLMClient,
    rubric: RubricView,
    resume_text: str,
    *,
    run_id: UUID | None = None,
    model: str | None = None,
    today: date | None = None,
) -> EvaluationResult:
    """`today` (default: the server's date) anchors "Present" in the resume's date ranges."""
    prompt = load_prompt(PROMPT_VERSION)
    keys = [c.key for c in rubric.criteria]
    schema = evaluation_schema(keys)
    messages = [
        {"role": "system", "content": prompt.system},
        {
            "role": "user",
            "content": render(
                prompt.user,
                {
                    "today": (today or date.today()).isoformat(),
                    "title": rubric.title,
                    "role_summary": rubric.role_summary,
                    "core_requirement": rubric.core_requirement,
                    "criteria_json": _criteria_json(rubric.criteria),
                    "resume_text": resume_text,
                },
            ),
        },
    ]

    async def call(purpose: str, msgs: list[dict[str, str]]) -> LLMResult[EvaluationOutput]:
        return await client.complete_json(
            purpose=purpose,
            prompt_version=PROMPT_VERSION,
            messages=msgs,
            output_model=EvaluationOutput,
            schema_name="evaluation",
            schema=schema,
            model=model,
            run_id=run_id,
        )

    call_ids: list[UUID] = []
    warnings: list[str] = []
    repaired = False
    try:
        result = await call("evaluate", messages)
    except LLMInvalidOutputError as error:
        call_ids.append(UUID(error.details["call_id"]))
        log.warning("evaluate_repair", reason="invalid_output")
        repaired = True
        result = await call(
            "repair",
            _repair_messages(
                prompt, messages, error.raw_text or "", str(error.details.get("errors", ""))
            ),
        )
    call_ids.append(result.call_id)

    by_key, missing, unknown, duplicates = reconcile(result.value, keys)
    if missing and not repaired:
        log.warning("evaluate_repair", reason="missing_keys", missing=missing)
        try:
            retry = await call(
                "repair",
                _repair_messages(
                    prompt,
                    messages,
                    result.raw_text,
                    f"these criterion keys were missing: {json.dumps(missing)}",
                ),
            )
        except LLMInvalidOutputError as error:
            call_ids.append(UUID(error.details["call_id"]))
            log.warning(
                "evaluate_repair_invalid", errors=str(error.details.get("errors", ""))[:300]
            )
        else:
            call_ids.append(retry.call_id)
            r_by_key, _, r_unknown, r_dupes = reconcile(retry.value, keys)
            for key in list(missing):
                if key in r_by_key:
                    by_key[key] = r_by_key[key]
            missing = [k for k in keys if k not in by_key]
            unknown += r_unknown
            duplicates += r_dupes
            # Holistic levels come from the first answer; the repair only fills gaps.

    if unknown:
        log.warning("evaluate_unknown_keys_dropped", keys=unknown)
        warnings.append(f"unknown_criterion_keys_dropped: {json.dumps(sorted(set(unknown)))}")
    if duplicates:
        warnings.append(f"duplicate_criterion_keys: {json.dumps(sorted(set(duplicates)))}")
    for key in missing:
        by_key[key] = CriterionResult(
            key=key,
            candidate_value="",
            evidence_strength="not_evidenced",
            outcome="Fail",
            reasoning=NOT_EVALUATED,
        )
    if missing:
        log.warning("evaluate_criteria_not_evaluated", keys=missing)
        warnings.append(f"criteria_not_evaluated: {json.dumps(missing)}")

    complete = result.value.model_copy(update={"criteria": [by_key[k] for k in keys]})
    return EvaluationResult(
        evaluation=complete, prompt_version=PROMPT_VERSION, call_ids=call_ids, warnings=warnings
    )
