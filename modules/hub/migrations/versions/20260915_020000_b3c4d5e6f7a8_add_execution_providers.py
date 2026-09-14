"""Add the global execution provider catalog.

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERSONAL_CODEX_ID = UUID("00000000-0000-0000-0000-000000000001")


def upgrade() -> None:
    op.create_table(
        "execution_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("adapter", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("availability_state", sa.String(30), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("availability_source", sa.String(100), nullable=True),
        sa.Column("availability_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("availability_note", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_execution_providers_available_at", "execution_providers", ["available_at"], unique=False)
    providers = sa.table(
        "execution_providers",
        sa.column("id", sa.Uuid()), sa.column("key", sa.String()), sa.column("name", sa.String()),
        sa.column("kind", sa.String()), sa.column("adapter", sa.String()), sa.column("enabled", sa.Boolean()),
        sa.column("availability_state", sa.String()), sa.column("revision", sa.Integer()),
    )
    op.bulk_insert(providers, [{"id": PERSONAL_CODEX_ID, "key": "personal-codex", "name": "Personal Codex", "kind": "codex", "adapter": "codex-github-mention", "enabled": True, "availability_state": "available", "revision": 1}])
    op.add_column("pipeline_runs", sa.Column("execution_provider_id", sa.Uuid(), nullable=True))
    op.execute(sa.text("UPDATE pipeline_runs SET execution_provider_id = :provider_id").bindparams(provider_id=PERSONAL_CODEX_ID))
    op.alter_column("pipeline_runs", "execution_provider_id", nullable=False)
    op.create_foreign_key("fk_pipeline_runs_execution_provider_id", "pipeline_runs", "execution_providers", ["execution_provider_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_pipeline_runs_execution_provider_id", "pipeline_runs", ["execution_provider_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_execution_provider_id", table_name="pipeline_runs")
    op.drop_constraint("fk_pipeline_runs_execution_provider_id", "pipeline_runs", type_="foreignkey")
    op.drop_column("pipeline_runs", "execution_provider_id")
    op.drop_index("ix_execution_providers_available_at", table_name="execution_providers")
    op.drop_table("execution_providers")
