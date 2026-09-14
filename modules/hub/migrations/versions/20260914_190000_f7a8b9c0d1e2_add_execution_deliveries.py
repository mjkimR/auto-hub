"""Persist each reconciled Codex mention delivery.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_number", sa.Integer(), nullable=False),
        sa.Column("cause", sa.String(length=30), nullable=False),
        sa.Column("comment_id", sa.String(length=255), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("delivery_number >= 1", name="ck_execution_deliveries_number_positive"),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comment_id"),
    )
    op.create_index("ix_execution_deliveries_execution_attempt_id", "execution_deliveries", ["execution_attempt_id"])
    op.create_index(
        "uq_execution_deliveries_attempt_number",
        "execution_deliveries",
        ["execution_attempt_id", "delivery_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_execution_deliveries_attempt_number", table_name="execution_deliveries")
    op.drop_index("ix_execution_deliveries_execution_attempt_id", table_name="execution_deliveries")
    op.drop_table("execution_deliveries")
