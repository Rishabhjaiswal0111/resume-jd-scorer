"""timings: stage durations for extraction, JD parsing, scoring, queueing and search

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-19

Existing rows: queue timestamps are backfilled from created_at (the column default would
otherwise stamp them with the migration time). Manual-mode llm_calls recorded latency 0
(hard-coded); that is unknown, not instant, so it becomes NULL. Runs left in a working
status by a cancelled worker (before cancellation was handled) are closed as ABANDONED.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_events",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_chars", sa.Integer(), nullable=False),
        sa.Column("term_count", sa.Integer(), nullable=False),
        sa.Column("total_candidates", sa.Integer(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.Column("top_match", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_search_events_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_events")),
    )
    op.create_index(
        "ix_search_events_owner_id_created_at",
        "search_events",
        ["owner_id", "created_at"],
        unique=False,
    )
    op.add_column("documents", sa.Column("extraction_ms", sa.Integer(), nullable=True))
    op.add_column(
        "job_candidates",
        sa.Column(
            "queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
    )
    op.add_column(
        "job_candidates", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "job_candidates", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "job_candidates", sa.Column("attempts", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "jobs",
        sa.Column(
            "parse_queued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.add_column("jobs", sa.Column("parse_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("parse_finished_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rubrics", sa.Column("parse_ms", sa.Integer(), nullable=True))
    op.add_column(
        "scoring_runs", sa.Column("timings", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


    op.execute("UPDATE jobs SET parse_queued_at = created_at")
    op.execute("UPDATE job_candidates SET queued_at = created_at")
    op.execute(
        "UPDATE llm_calls SET latency_ms = NULL "
        "WHERE provider = 'manual' AND latency_ms = 0 AND NOT cache_hit"
    )
    op.execute(
        "UPDATE scoring_runs SET status = 'failed', error_code = 'ABANDONED', "
        "error_message = 'The worker stopped before this run finished' "
        "WHERE status NOT IN ('completed', 'failed') AND created_at < now() - interval '1 hour'"
    )


def downgrade() -> None:
    op.drop_column("scoring_runs", "timings")
    op.drop_column("rubrics", "parse_ms")
    op.drop_column("jobs", "parse_finished_at")
    op.drop_column("jobs", "parse_started_at")
    op.drop_column("jobs", "parse_queued_at")
    op.drop_column("job_candidates", "attempts")
    op.drop_column("job_candidates", "finished_at")
    op.drop_column("job_candidates", "started_at")
    op.drop_column("job_candidates", "queued_at")
    op.drop_column("documents", "extraction_ms")
    op.drop_index("ix_search_events_owner_id_created_at", table_name="search_events")
    op.drop_table("search_events")
