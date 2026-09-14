"""Remove the Linear integration and key pipeline runs by pull request.

Deletes Linear connectors, the project mapping columns, and every stored Linear field. Existing
pipeline runs were keyed by Linear issues and cannot be mapped to pull requests; no external
dispatch was ever enabled for them, so they are deleted with their attempts.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
ACTIVE = sa.text("state IN ('queued', 'dispatching', 'implementing', 'awaiting_ci', 'paused')")
REMOVED_FIELD = "linear_project_id"

schedules = sa.table(
    "schedule_configs", sa.column("id", sa.Uuid()), sa.column("task_func", sa.String()), sa.column("payload", JSON_TYPE)
)
task_states = sa.table("task_states", sa.column("config_id", sa.Uuid()), sa.column("data", JSON_TYPE))
projects = sa.table("project_connections", sa.column("id", sa.Uuid()), sa.column(REMOVED_FIELD, sa.Uuid()))


def _create_active_project_index() -> None:
    op.create_index(
        "uq_pipeline_runs_active_project",
        "pipeline_runs",
        ["project_id"],
        unique=True,
        postgresql_where=ACTIVE,
        sqlite_where=ACTIVE,
    )


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("DELETE FROM execution_attempts")
    op.execute("DELETE FROM pipeline_runs")
    # Batch mode rebuilds the table on SQLite; recreate the partial index explicitly so its predicate survives.
    op.drop_index("uq_pipeline_runs_active_project", table_name="pipeline_runs")
    with op.batch_alter_table("pipeline_runs") as batch:
        batch.drop_column("linear_issue_id")
        batch.drop_column("linear_issue_identifier")
        batch.drop_column("linear_issue_snapshot")
        batch.add_column(sa.Column("pull_snapshot", JSON_TYPE, nullable=False))
        batch.alter_column("pull_number", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("pull_url", existing_type=sa.String(2048), nullable=False)
    _create_active_project_index()
    op.create_index(
        "uq_pipeline_runs_active_pull",
        "pipeline_runs",
        ["project_id", "pull_number"],
        unique=True,
        postgresql_where=ACTIVE,
        sqlite_where=ACTIVE,
    )

    with op.batch_alter_table("project_connections") as batch:
        batch.drop_column("linear_connector_id")
        batch.drop_column(REMOVED_FIELD)
    op.execute("DELETE FROM connectors WHERE provider = 'linear'")

    for row in bind.execute(sa.select(schedules).where(schedules.c.task_func == "pipeline.observe")).mappings().all():
        payload = row["payload"]
        if isinstance(payload, dict) and REMOVED_FIELD in payload:
            payload = {key: value for key, value in payload.items() if key != REMOVED_FIELD}
            bind.execute(schedules.update().where(schedules.c.id == row["id"]).values(payload=payload))

    for row in bind.execute(sa.select(task_states)).mappings().all():
        data = row["data"]
        config = data.get("config") if isinstance(data, dict) and data.get("kind") == "pipeline_observation" else None
        if isinstance(config, dict) and REMOVED_FIELD in config:
            config = {key: value for key, value in config.items() if key != REMOVED_FIELD}
            bind.execute(
                task_states.update()
                .where(task_states.c.config_id == row["config_id"])
                .values(data={**data, "config": config})
            )


def downgrade() -> None:
    """Restore the previous schema. Deleted connectors and runs are not restored.

    Pull-request runs cannot be represented by the Linear-keyed schema and are deleted. Mapping IDs
    are placeholders because the original values are gone; stored observation reports without the
    field are treated as stale by the previous reader.
    """
    bind = op.get_bind()

    with op.batch_alter_table("project_connections") as batch:
        batch.add_column(sa.Column(REMOVED_FIELD, sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("linear_connector_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_project_connections_linear_connector_id", "connectors", ["linear_connector_id"], ["id"], ondelete="RESTRICT"
        )
    for row in bind.execute(sa.select(projects.c.id)).mappings().all():
        bind.execute(projects.update().where(projects.c.id == row["id"]).values({REMOVED_FIELD: uuid4()}))
    with op.batch_alter_table("project_connections") as batch:
        batch.alter_column(REMOVED_FIELD, existing_type=sa.Uuid(), nullable=False)
        batch.create_unique_constraint("uq_project_connections_linear_project_id", [REMOVED_FIELD])

    for row in bind.execute(sa.select(schedules).where(schedules.c.task_func == "pipeline.observe")).mappings().all():
        payload = row["payload"]
        if isinstance(payload, dict) and REMOVED_FIELD not in payload:
            bind.execute(
                schedules.update()
                .where(schedules.c.id == row["id"])
                .values(payload={**payload, REMOVED_FIELD: str(uuid4())})
            )

    op.execute("DELETE FROM execution_attempts")
    op.execute("DELETE FROM pipeline_runs")
    op.drop_index("uq_pipeline_runs_active_pull", table_name="pipeline_runs")
    op.drop_index("uq_pipeline_runs_active_project", table_name="pipeline_runs")
    with op.batch_alter_table("pipeline_runs") as batch:
        batch.drop_column("pull_snapshot")
        batch.add_column(sa.Column("linear_issue_id", sa.Uuid(), nullable=False))
        batch.add_column(sa.Column("linear_issue_identifier", sa.String(100), nullable=False))
        batch.add_column(sa.Column("linear_issue_snapshot", JSON_TYPE, nullable=False))
        batch.alter_column("pull_number", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("pull_url", existing_type=sa.String(2048), nullable=True)
        batch.create_unique_constraint("uq_pipeline_runs_linear_issue_id", ["linear_issue_id"])
    _create_active_project_index()
