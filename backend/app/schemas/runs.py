"""API response shapes for scoring runs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Point(BaseModel):
    text: str
    source: str
    operator: str | None
    importance: str | None
    outcome: str


class CriterionView(BaseModel):
    key: str
    name: str
    operator: str
    importance: str
    outcome: str
    llm_outcome: str
    evidence_strength: str
    candidate_value: str
    reasoning: str
    weight: str
    earned: str
    forced: str | None
    knockout: bool
    group: str


class ScreeningQuestion(BaseModel):
    key: str
    name: str
    reasoning: str


class GroupAdjustment(BaseModel):
    group: str
    criteria: list[str]
    relief: str


class Holistic(BaseModel):
    level: str
    summary: str


class CostView(BaseModel):
    run_llm_cost_usd: str | None
    rubric_cost_share_usd: str | None
    provider_reported_usd: str | None
    llm_calls: int


class RunDetail(BaseModel):
    id: UUID
    status: str
    error_code: str | None
    error_message: str | None
    score: str | None
    verdict: str | None
    role_title: str | None
    model: str
    engine_version: str
    role_overlap: Holistic | None
    core_requirement: Holistic | None
    pros: list[Point]
    cons: list[Point]
    criteria: list[CriterionView]
    screening: list[ScreeningQuestion]
    group_adjustments: list[GroupAdjustment]
    warnings: list[str]
    cost: CostView
    latency_ms: int | None
    created_at: datetime
