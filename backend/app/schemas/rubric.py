"""Rubric schemas (PLAN.md §7.1). Produced by the JD-parse LLM call."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Attribute = Literal["hard_skills", "soft_skills", "experience", "education", "location", "other"]
Operator = Literal["must_have", "preferred", "nice_to_have", "must_avoid", "may_avoid"]
Importance = Literal["high", "normal"]

OPERATORS: tuple[Operator, ...] = (
    "must_have",
    "preferred",
    "nice_to_have",
    "must_avoid",
    "may_avoid",
)

KEY_PATTERN = r"^c_[a-z0-9_]{1,60}$"


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=KEY_PATTERN, description="snake_case id starting with c_")
    name: str = Field(min_length=1, max_length=120)
    attribute: Attribute
    operator: Operator
    importance: Importance
    values: list[str] = Field(description="concrete skills/values the criterion looks for")
    source_excerpt: str = Field(description="verbatim JD text this criterion came from")


class RubricOutput(BaseModel):
    """What the JD-parse call must return."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    role_summary: str = Field(min_length=1, description="2-3 sentences: what the role does")
    core_requirement: str = Field(
        min_length=1, description="the single capability the role cannot do without"
    )
    criteria: list[Criterion]
