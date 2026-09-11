"""Add durable pipeline runs and execution attempts.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("project_connections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("project_revision", sa.Integer(), nullable=False),
        sa.Column("linear_issue_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("linear_issue_identifier", sa.String(100), nullable=False),
        sa.Column("linear_issue_snapshot", json_type, nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("pause_reason", sa.Text(), nullable=True),
        sa.Column("branch", sa.String(255), nullable=False),
        sa.Column("pull_number", sa.Integer(), nullable=True),
        sa.Column("pull_url", sa.String(2048), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(255), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_pipeline_runs_revision_positive"),
    )
    op.create_index("ix_pipeline_runs_state", "pipeline_runs", ["state"])
    op.create_index("ix_pipeline_runs_lease_expires_at", "pipeline_runs", ["lease_expires_at"])
    op.create_index("ix_pipeline_runs_project_created", "pipeline_runs", ["project_id", "created_at"])
    active = sa.text("state IN ('queued', 'dispatching', 'implementing', 'awaiting_ci', 'paused')")
    op.create_index(
        "uq_pipeline_runs_active_project",
        "pipeline_runs",
        ["project_id"],
        unique=True,
        postgresql_where=active,
        sqlite_where=active,
    )

    op.create_table(
        "execution_attempts",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "pipeline_run_id",
            sa.Uuid(),
            sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("request_snapshot", json_type, nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False, unique=True),
        sa.Column("external_correlation_id", sa.String(255), nullable=True, unique=True),
        sa.Column("external_status", sa.String(100), nullable=True),
        sa.Column("conversation_url", sa.String(2048), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("attempt_number >= 1", name="ck_execution_attempts_number_positive"),
    )
    op.create_index("ix_execution_attempts_pipeline_run_id", "execution_attempts", ["pipeline_run_id"])
    op.create_index(
        "uq_execution_attempts_run_number",
        "execution_attempts",
        ["pipeline_run_id", "attempt_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("execution_attempts")
    op.drop_table("pipeline_runs")
