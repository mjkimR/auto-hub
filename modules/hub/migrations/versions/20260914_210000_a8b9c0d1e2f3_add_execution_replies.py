"""Persist trusted Codex replies independently of task deliveries.

Revision ID: c9d0e1f2a3b4
Revises: a8b9c0d1e2f3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_replies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.String(length=255), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("is_quota_limit", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comment_id"),
    )
    op.create_index("ix_execution_replies_execution_attempt_id", "execution_replies", ["execution_attempt_id"])


def downgrade() -> None:
    op.drop_index("ix_execution_replies_execution_attempt_id", table_name="execution_replies")
    op.drop_table("execution_replies")
