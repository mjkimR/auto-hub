"""Record GitHub webhook delivery IDs for idempotent processing.

Revision ID: d0e1f2a3b4c5
Revises: b9c0d1e2f3a4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "b9c0d1e2f3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "github_webhook_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("delivery_id", sa.String(length=255), nullable=False),
        sa.Column("event", sa.String(length=100), nullable=False),
        sa.Column("repository", sa.String(length=255), nullable=True),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id"),
    )
    op.create_index("ix_github_webhook_deliveries_repository", "github_webhook_deliveries", ["repository"])


def downgrade() -> None:
    op.drop_index("ix_github_webhook_deliveries_repository", table_name="github_webhook_deliveries")
    op.drop_table("github_webhook_deliveries")
