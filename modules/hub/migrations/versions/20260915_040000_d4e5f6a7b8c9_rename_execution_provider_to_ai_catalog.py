"""Rename the execution provider storage to AI catalog.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("fk_pipeline_runs_execution_provider_id", "pipeline_runs", type_="foreignkey")
    op.drop_index("ix_pipeline_runs_execution_provider_id", table_name="pipeline_runs")
    op.drop_index("ix_execution_providers_available_at", table_name="execution_providers")
    op.rename_table("execution_providers", "ai_catalogs")
    op.create_index("ix_ai_catalogs_available_at", "ai_catalogs", ["available_at"], unique=False)
    op.alter_column("pipeline_runs", "execution_provider_id", new_column_name="ai_catalog_id")
    op.create_foreign_key("fk_pipeline_runs_ai_catalog_id", "pipeline_runs", "ai_catalogs", ["ai_catalog_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_pipeline_runs_ai_catalog_id", "pipeline_runs", ["ai_catalog_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_ai_catalog_id", table_name="pipeline_runs")
    op.drop_constraint("fk_pipeline_runs_ai_catalog_id", "pipeline_runs", type_="foreignkey")
    op.drop_index("ix_ai_catalogs_available_at", table_name="ai_catalogs")
    op.alter_column("pipeline_runs", "ai_catalog_id", new_column_name="execution_provider_id")
    op.rename_table("ai_catalogs", "execution_providers")
    op.create_index("ix_execution_providers_available_at", "execution_providers", ["available_at"], unique=False)
    op.create_foreign_key("fk_pipeline_runs_execution_provider_id", "pipeline_runs", "execution_providers", ["execution_provider_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_pipeline_runs_execution_provider_id", "pipeline_runs", ["execution_provider_id"], unique=False)
