"""ORM models (docs/PLAN.md §6 and §8).

Import every model here so Alembic autogenerate sees it.
Enum-like columns are TEXT + CHECK constraints (cheaper to evolve than PG enums).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

MONEY = Numeric(12, 8)

DOCUMENT_KINDS = ("jd", "resume")
RUN_STATUSES = (
    "created",
    "extracting",
    "parsing_jd",
    "evaluating",
    "scoring",
    "completed",
    "failed",
)
LLM_PURPOSES = ("jd_parse", "evaluate", "repair", "eval")
LLM_CALL_STATUSES = ("success", "invalid_output", "error")


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("kind", "sha256", name="uq_documents_kind_sha256"),
        CheckConstraint(_in("kind", DOCUMENT_KINDS), name="kind"),
    )

    kind: Mapped[str] = mapped_column(String(16))
    original_filename: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(Text)
    page_count: Mapped[int] = mapped_column(Integer)
    extractor: Mapped[str] = mapped_column(String(32))
    text_storage_key: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False)


class Rubric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rubrics"
    __table_args__ = (
        UniqueConstraint("jd_document_id", "version", name="uq_rubrics_jd_document_id_version"),
    )

    jd_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(Text)
    core_requirement: Mapped[str] = mapped_column(Text)
    role_summary: Mapped[str] = mapped_column(Text)
    criteria: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    prompt_version: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(Text)
    # use_alter: rubrics <-> llm_calls reference each other.
    llm_call_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("llm_calls.id", use_alter=True, name="fk_rubrics_llm_call_id_llm_calls")
    )
    created_by: Mapped[str] = mapped_column(String(64), default="llm")


class ScoringRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scoring_runs"
    __table_args__ = (CheckConstraint(_in("status", RUN_STATUSES), name="status"),)

    # Nullable: a run exists from the first step (PLAN.md §4) and these are filled in as
    # extraction / JD parsing complete, so failures at those steps are still recorded.
    jd_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    resume_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id"), index=True
    )
    rubric_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rubrics.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="created", index=True)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    pros: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    cons: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    role_overlap: Mapped[str | None] = mapped_column(Text)
    core_demonstration: Mapped[str | None] = mapped_column(Text)
    # Validated LLM evaluation (after repair). Replay recomputes the score from this alone.
    evaluation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String(64))
    engine_version: Mapped[str] = mapped_column(String(32))
    llm_cost_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    rubric_cost_share_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    replay_of_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scoring_runs.id"))


class CriterionEvaluation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "criterion_evaluations"
    __table_args__ = (
        UniqueConstraint("run_id", "criterion_key", name="uq_criterion_evaluations_run_key"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scoring_runs.id", ondelete="CASCADE"), index=True
    )
    criterion_key: Mapped[str] = mapped_column(String(128))
    operator: Mapped[str] = mapped_column(String(32))
    importance: Mapped[str] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(32))
    llm_outcome: Mapped[str] = mapped_column(String(32))
    evidence_strength: Mapped[str] = mapped_column(String(32))
    candidate_value: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)
    weight: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    earned: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    was_forced_fail: Mapped[bool] = mapped_column(Boolean, default=False)


class LLMCall(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cost ledger: one row per LLM attempt (success, failure or cache hit). PLAN.md §8."""

    __tablename__ = "llm_calls"
    __table_args__ = (
        CheckConstraint(_in("purpose", LLM_PURPOSES), name="purpose"),
        CheckConstraint(_in("status", LLM_CALL_STATUSES), name="status"),
        Index("ix_llm_calls_request_hash_status", "request_hash", "status"),
    )

    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scoring_runs.id"), index=True)
    rubric_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rubrics.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))

    input_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)

    price_input_per_m: Mapped[Decimal | None] = mapped_column(MONEY)
    price_cached_per_m: Mapped[Decimal | None] = mapped_column(MONEY)
    price_output_per_m: Mapped[Decimal | None] = mapped_column(MONEY)
    model_price_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_prices.id"))

    # NULL only when the price was missing (PRICE_MISSING); 0 for cache hits and failed
    # attempts that returned no usage.
    cost_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    provider_reported_cost_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    cost_delta_usd: Mapped[Decimal | None] = mapped_column(
        MONEY, Computed("provider_reported_cost_usd - cost_usd", persisted=True)
    )
    provider_request_id: Mapped[str | None] = mapped_column(Text)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_source_call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("llm_calls.id"))

    status: Mapped[str] = mapped_column(String(16))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    request_key: Mapped[str | None] = mapped_column(Text)
    response_key: Mapped[str | None] = mapped_column(Text)


class ModelPrice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """USD per 1M tokens, valid on [effective_from, effective_to)."""

    __tablename__ = "model_prices"
    __table_args__ = (
        UniqueConstraint(
            "provider", "model", "effective_from", name="uq_model_prices_provider_model_from"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from", name="effective_range"
        ),
    )

    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(Text)
    input_per_m: Mapped[Decimal] = mapped_column(MONEY)
    cached_input_per_m: Mapped[Decimal] = mapped_column(MONEY)
    output_per_m: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(Text)


__all__ = [
    "Base",
    "CriterionEvaluation",
    "Document",
    "LLMCall",
    "ModelPrice",
    "Rubric",
    "ScoringRun",
]
