"""accounts, jobs, candidates (docs/plan-jobs-and-search.md)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-19

Users + sessions, and the workspace tables that own jobs and candidates. candidates has a
generated tsvector with a GIN index for search. Existing documents / rubrics / runs are
unchanged and stay shared.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "candidates",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("resume_document_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', search_text)", persisted=True),
            nullable=False,
        ),
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
            name=op.f("fk_candidates_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resume_document_id"],
            ["documents.id"],
            name=op.f("fk_candidates_resume_document_id_documents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidates")),
        sa.UniqueConstraint(
            "owner_id", "resume_document_id", name="uq_candidates_owner_id_resume_document_id"
        ),
    )
    op.create_index(
        "ix_candidates_owner_id_created_at", "candidates", ["owner_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_candidates_search_vector",
        "candidates",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False)
    op.create_table(
        "jobs",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("jd_document_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rubric_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'parsing', 'ready', 'failed')", name=op.f("ck_jobs_status")
        ),
        sa.ForeignKeyConstraint(
            ["jd_document_id"], ["documents.id"], name=op.f("fk_jobs_jd_document_id_documents")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_jobs_owner_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["rubric_id"], ["rubrics.id"], name=op.f("fk_jobs_rubric_id_rubrics")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("owner_id", "jd_document_id", name="uq_jobs_owner_id_jd_document_id"),
    )
    op.create_index("ix_jobs_owner_id_created_at", "jobs", ["owner_id", "created_at"], unique=False)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_table(
        "job_candidates",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("source IN ('upload', 'search')", name=op.f("ck_job_candidates_source")),
        sa.CheckConstraint(
            "status IN ('queued', 'scoring', 'scored', 'failed')",
            name=op.f("ck_job_candidates_status"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_job_candidates_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_job_candidates_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["scoring_runs.id"], name=op.f("fk_job_candidates_run_id_scoring_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_candidates")),
        sa.UniqueConstraint("job_id", "candidate_id", name="uq_job_candidates_job_id_candidate_id"),
    )
    op.create_index(
        op.f("ix_job_candidates_candidate_id"), "job_candidates", ["candidate_id"], unique=False
    )
    op.create_index(op.f("ix_job_candidates_job_id"), "job_candidates", ["job_id"], unique=False)
    op.create_index(op.f("ix_job_candidates_run_id"), "job_candidates", ["run_id"], unique=False)
    op.create_index(op.f("ix_job_candidates_status"), "job_candidates", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_candidates_status"), table_name="job_candidates")
    op.drop_index(op.f("ix_job_candidates_run_id"), table_name="job_candidates")
    op.drop_index(op.f("ix_job_candidates_job_id"), table_name="job_candidates")
    op.drop_index(op.f("ix_job_candidates_candidate_id"), table_name="job_candidates")
    op.drop_table("job_candidates")
    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_index("ix_jobs_owner_id_created_at", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_candidates_search_vector", table_name="candidates", postgresql_using="gin")
    op.drop_index("ix_candidates_owner_id_created_at", table_name="candidates")
    op.drop_table("candidates")
    op.drop_table("users")
