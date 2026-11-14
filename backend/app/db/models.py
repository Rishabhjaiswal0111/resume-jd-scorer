"""ORM models.

Import every model here so Alembic autogenerate sees it.
Phase 1.1 adds: documents, rubrics, scoring_runs, criterion_evaluations,
llm_calls, model_prices (see docs/PLAN.md §6 and §8).
"""

from app.db.base import Base

__all__ = ["Base"]
