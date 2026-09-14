"""Set server_default now() for delivery and reply timestamp columns.

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("execution_deliveries", "execution_replies", "github_webhook_deliveries"):
        op.alter_column(table, "created_at", server_default=sa.func.now())
        op.alter_column(table, "updated_at", server_default=sa.func.now())


def downgrade() -> None:
    for table in ("execution_deliveries", "execution_replies", "github_webhook_deliveries"):
        op.alter_column(table, "created_at", server_default=None)
        op.alter_column(table, "updated_at", server_default=None)
