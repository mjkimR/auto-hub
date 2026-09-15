"""Capture the GitHub binding a pipeline run was enrolled with.

Existing runs are backfilled only while their project is still at the enrolled revision; others stay NULL, so a
resume after a project change requires enrolling the pull request again.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pipeline_runs", sa.Column("github_repository", sa.String(255), nullable=True))
    op.add_column("pipeline_runs", sa.Column("github_connector_id", sa.Uuid(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE pipeline_runs SET
                github_repository = (
                    SELECT projects.github_repository FROM projects
                    WHERE projects.id = pipeline_runs.project_id
                      AND projects.revision = pipeline_runs.project_revision
                ),
                github_connector_id = (
                    SELECT projects.github_connector_id FROM projects
                    WHERE projects.id = pipeline_runs.project_id
                      AND projects.revision = pipeline_runs.project_revision
                )
            """
        )
    )


def downgrade() -> None:
    op.drop_column("pipeline_runs", "github_connector_id")
    op.drop_column("pipeline_runs", "github_repository")
