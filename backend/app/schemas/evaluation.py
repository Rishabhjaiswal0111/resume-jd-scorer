"""Evaluation schemas (PLAN.md §7.2). Produced by the evaluate LLM call."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RoleOverlapLevel = Literal["Strong", "Moderate", "Weak", "None"]
CoreLevel = Literal["Clear", "Partial", "Weak", "None"]
EvidenceStrength = Literal["evidenced", "partial_evidence", "not_evidenced", "contradicted"]
Outcome = Literal["Full Pass", "Partial Pass", "Fail"]


class RoleOverlap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: RoleOverlapLevel
    summary: str = Field(description="<= 30 words")


class CoreRequirementAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: CoreLevel
    summary: str = Field(description="<= 40 words")


class CriterionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    candidate_value: str = Field(description="what the resume shows for this criterion")
    evidence_strength: EvidenceStrength
    outcome: Outcome
    reasoning: str = Field(description="<= 40 words, recruiter-facing")


class EvaluationOutput(BaseModel):
    """What the evaluate call must return."""

    model_config = ConfigDict(extra="forbid")

    role_overlap: RoleOverlap
    core_requirement: CoreRequirementAssessment
    criteria: list[CriterionResult]
