"""add task_states

Revision ID: b2c3d4e5f6a7
Revises: 3ed9535ae4d9
Create Date: 2026-07-08 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = '3ed9535ae4d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'task_states',
        sa.Column('config_id', sa.Uuid(), nullable=False, comment='ScheduleConfig id this state belongs to (from the task execution context).'),
        sa.Column('data', sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql'), nullable=False, comment='Opaque, task-owned state blob.'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('config_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('task_states')
