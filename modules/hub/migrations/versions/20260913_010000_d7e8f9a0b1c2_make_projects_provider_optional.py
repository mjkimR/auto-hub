"""Make projects independent containers with optional GitHub and Linear connections.

Revision ID: d7e8f9a0b1c2
Revises: c4d5e6f7a8b9
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("project_connections", "projects")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column("projects", "repository", new_column_name="github_repository")
        op.alter_column("projects", "github_repository", nullable=True)
        op.alter_column("projects", "linear_project_id", nullable=True)
        op.alter_column("projects", "github_connector_id", nullable=True)
        op.alter_column("projects", "verification", nullable=True)
        op.drop_constraint("ck_project_repository_lowercase", "projects", type_="check")
    else:
        # SQLite needs a table rebuild for nullable changes and column renames.
        with op.batch_alter_table("projects", recreate="always") as batch:
            batch.alter_column("repository", new_column_name="github_repository", existing_type=sa.String(255), nullable=True)
            batch.alter_column("linear_project_id", nullable=True)
            batch.alter_column("github_connector_id", nullable=True)
            batch.alter_column("verification", nullable=True)
            batch.drop_constraint("ck_project_repository_lowercase", type_="check")


def downgrade() -> None:
    # A standalone project cannot be represented in the old required-connection shape.
    bind = op.get_bind()
    missing = bind.execute(
        sa.text("SELECT count(*) FROM projects WHERE github_repository IS NULL OR linear_project_id IS NULL")
    ).scalar_one()
    if missing:
        raise RuntimeError("Cannot downgrade while standalone or partially connected projects exist")
    if bind.dialect.name == "postgresql":
        op.alter_column("projects", "github_repository", nullable=False)
        op.alter_column("projects", "linear_project_id", nullable=False)
        op.alter_column("projects", "github_connector_id", nullable=False)
        op.alter_column("projects", "verification", nullable=False)
        op.alter_column("projects", "github_repository", new_column_name="repository")
        op.create_check_constraint("ck_project_repository_lowercase", "projects", "repository = lower(repository)")
    else:
        with op.batch_alter_table("projects", recreate="always") as batch:
            batch.alter_column("github_repository", new_column_name="repository", existing_type=sa.String(255), nullable=False)
            batch.alter_column("linear_project_id", nullable=False)
            batch.alter_column("github_connector_id", nullable=False)
            batch.alter_column("verification", nullable=False)
            batch.create_check_constraint("ck_project_repository_lowercase", "repository = lower(repository)")
    op.rename_table("projects", "project_connections")
