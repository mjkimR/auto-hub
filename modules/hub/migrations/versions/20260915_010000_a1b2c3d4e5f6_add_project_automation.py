"""Add configurable per-project GitHub automation defaults.

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.add_column(
        "projects",
        sa.Column(
            "automation",
            json_type,
            nullable=False,
            server_default=sa.text("'{\"auto_merge\": true, \"merge_method\": \"squash\", \"auto_fix_ci\": true, \"auto_fix_conflicts\": true, \"auto_enroll_on_trigger\": true, \"dispatch_interval_seconds\": 60}'"),
        ),
    )
    op.alter_column("projects", "automation", server_default=None)


def downgrade() -> None:
    op.drop_column("projects", "automation")
