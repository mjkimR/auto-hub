"""Add configurable AI catalog refresh cycles.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_catalogs", sa.Column("short_refresh_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("ai_catalogs", sa.Column("short_refresh_cycle_minutes", sa.Integer(), nullable=False, server_default="300"))
    op.add_column("ai_catalogs", sa.Column("long_refresh_cycle_minutes", sa.Integer(), nullable=False, server_default="10080"))
    op.add_column("ai_catalogs", sa.Column("refresh_jitter_minutes", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("ai_catalogs", sa.Column("short_refresh_failure_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_catalogs", sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("ai_catalogs", "short_refresh_enabled", server_default=None)
    op.alter_column("ai_catalogs", "short_refresh_cycle_minutes", server_default=None)
    op.alter_column("ai_catalogs", "long_refresh_cycle_minutes", server_default=None)
    op.alter_column("ai_catalogs", "refresh_jitter_minutes", server_default=None)
    op.alter_column("ai_catalogs", "short_refresh_failure_count", server_default=None)


def downgrade() -> None:
    op.drop_column("ai_catalogs", "last_refreshed_at")
    op.drop_column("ai_catalogs", "short_refresh_failure_count")
    op.drop_column("ai_catalogs", "refresh_jitter_minutes")
    op.drop_column("ai_catalogs", "long_refresh_cycle_minutes")
    op.drop_column("ai_catalogs", "short_refresh_cycle_minutes")
    op.drop_column("ai_catalogs", "short_refresh_enabled")
