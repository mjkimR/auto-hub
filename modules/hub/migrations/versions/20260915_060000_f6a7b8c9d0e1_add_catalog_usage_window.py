"""Track the first task of an AI catalog's provider usage window.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_catalogs", sa.Column("usage_window_started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_catalogs", "usage_window_started_at")
