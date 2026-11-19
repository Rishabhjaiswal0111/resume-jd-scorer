"""llm_calls.cache_write_tokens

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-17

Anthropic reports prompt-cache writes separately (billed at 1.25x input). The cost was
already computed with them; storing them lets cost be recomputed from stored tokens.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("cache_write_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_calls", "cache_write_tokens")
