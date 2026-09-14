"""Allow one active run per pull request instead of per project.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_pipeline_runs_active_project", table_name="pipeline_runs")


def downgrade() -> None:
    op.create_index(
        "uq_pipeline_runs_active_project",
        "pipeline_runs",
        ["project_id"],
        unique=True,
        sqlite_where=sa.text("state IN ('queued', 'dispatching', 'implementing', 'awaiting_ci', 'paused', 'blocked')"),
        postgresql_where=sa.text("state IN ('queued', 'dispatching', 'implementing', 'awaiting_ci', 'paused', 'blocked')"),
    )
