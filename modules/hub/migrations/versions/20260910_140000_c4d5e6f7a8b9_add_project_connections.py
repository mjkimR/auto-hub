"""Add persistent project connections; legacy payload import is explicit and transactional.

Revision ID: c4d5e6f7a8b9
Revises: 8c3d1e4f5a6b
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "8c3d1e4f5a6b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "project_connections",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("repository", sa.String(255), nullable=False, unique=True),
        sa.Column("linear_project_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("github_connector_id", sa.Uuid(), sa.ForeignKey("connectors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("linear_connector_id", sa.Uuid(), sa.ForeignKey("connectors.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("verification", json_type, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.String(50), nullable=True),
        sa.Column("template_version", sa.String(50), nullable=True),
        sa.Column("last_check", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("repository = lower(repository)", name="ck_project_repository_lowercase"),
    )


def downgrade() -> None:
    # Do not strand schedules that have already adopted project references.
    bind = op.get_bind()
    projects = sa.table("project_connections", sa.column("id", sa.Uuid()), sa.column("repository"),
        sa.column("linear_project_id", sa.Uuid()), sa.column("github_connector_id", sa.Uuid()), sa.column("verification", sa.JSON()))
    schedules = sa.table("schedule_configs", sa.column("id", sa.Uuid()), sa.column("task_func"), sa.column("payload", sa.JSON()))
    from uuid import UUID

    for row in bind.execute(sa.select(schedules).where(schedules.c.task_func == "pipeline.observe_project")).mappings():
        payload = row["payload"]
        project = bind.execute(sa.select(projects).where(projects.c.id == UUID(payload["project_id"]))).mappings().one()
        bind.execute(schedules.update().where(schedules.c.id == row["id"]).values(
            task_func="pipeline.observe", payload={
                "repository": project["repository"], "linear_project_id": str(project["linear_project_id"]),
                "github_connector_id": str(project["github_connector_id"]), "verification": project["verification"],
                "pull_numbers": payload["pull_numbers"],
            },
        ))
    op.drop_table("project_connections")
