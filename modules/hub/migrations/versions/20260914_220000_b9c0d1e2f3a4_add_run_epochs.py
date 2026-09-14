"""Add retry epochs for bounded CI and conflict fix loops.

Revision ID: b9c0d1e2f3a4
Revises: c9d0e1f2a3b4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9c0d1e2f3a4"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("pipeline_runs") as batch:
        batch.add_column(sa.Column("epoch", sa.Integer(), nullable=False, server_default="1"))
        batch.create_check_constraint("ck_pipeline_runs_epoch_positive", "epoch >= 1")
    with op.batch_alter_table("execution_attempts") as batch:
        batch.add_column(sa.Column("epoch", sa.Integer(), nullable=False, server_default="1"))
        batch.create_check_constraint("ck_execution_attempts_epoch_positive", "epoch >= 1")


def downgrade() -> None:
    with op.batch_alter_table("execution_attempts") as batch:
        batch.drop_constraint("ck_execution_attempts_epoch_positive", type_="check")
        batch.drop_column("epoch")
    with op.batch_alter_table("pipeline_runs") as batch:
        batch.drop_constraint("ck_pipeline_runs_epoch_positive", type_="check")
        batch.drop_column("epoch")
