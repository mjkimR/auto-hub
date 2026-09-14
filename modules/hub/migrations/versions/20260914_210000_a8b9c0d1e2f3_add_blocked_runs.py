"""Keep manually blocked runs active.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ACTIVE = sa.text("state IN ('queued', 'dispatching', 'implementing', 'awaiting_ci', 'paused')")
ACTIVE = sa.text("state IN ('queued', 'dispatching', 'implementing', 'awaiting_ci', 'paused', 'blocked')")


def _indexes(predicate: sa.TextClause) -> None:
    op.create_index(
        "uq_pipeline_runs_active_project",
        "pipeline_runs",
        ["project_id"],
        unique=True,
        postgresql_where=predicate,
        sqlite_where=predicate,
    )
    op.create_index(
        "uq_pipeline_runs_active_pull",
        "pipeline_runs",
        ["project_id", "pull_number"],
        unique=True,
        postgresql_where=predicate,
        sqlite_where=predicate,
    )


def upgrade() -> None:
    op.add_column("pipeline_runs", sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_pipeline_runs_next_action_at", "pipeline_runs", ["next_action_at"])
    op.drop_index("uq_pipeline_runs_active_pull", table_name="pipeline_runs")
    op.drop_index("uq_pipeline_runs_active_project", table_name="pipeline_runs")
    _indexes(ACTIVE)


def downgrade() -> None:
    op.drop_index("uq_pipeline_runs_active_pull", table_name="pipeline_runs")
    op.drop_index("uq_pipeline_runs_active_project", table_name="pipeline_runs")
    _indexes(OLD_ACTIVE)
    op.drop_index("ix_pipeline_runs_next_action_at", table_name="pipeline_runs")
    op.drop_column("pipeline_runs", "next_action_at")
