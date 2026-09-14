"""Add AI catalog gateway capacity and quota controls.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("execution_providers", sa.Column("configured_concurrency", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("execution_providers", sa.Column("probe_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("execution_providers", sa.Column("probe_window_minutes", sa.Integer(), nullable=False, server_default="10"))
    op.execute("UPDATE execution_providers SET availability_state = 'normal' WHERE availability_state = 'available'")
    op.execute("UPDATE execution_providers SET availability_state = 'quota_blocked' WHERE availability_state = 'quota_limited'")
    op.add_column("pipeline_runs", sa.Column("quota_block_count", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("execution_providers", "configured_concurrency", server_default=None)
    op.alter_column("execution_providers", "probe_window_minutes", server_default=None)
    op.alter_column("pipeline_runs", "quota_block_count", server_default=None)


def downgrade() -> None:
    op.drop_column("pipeline_runs", "quota_block_count")
    op.drop_column("execution_providers", "probe_window_minutes")
    op.drop_column("execution_providers", "probe_started_at")
    op.drop_column("execution_providers", "configured_concurrency")
