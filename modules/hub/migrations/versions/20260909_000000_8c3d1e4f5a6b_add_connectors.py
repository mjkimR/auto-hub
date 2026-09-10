"""add connectors

Revision ID: 8c3d1e4f5a6b
Revises: b2c3d4e5f6a7
Create Date: 2026-09-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision: str = "8c3d1e4f5a6b"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connectors",
        sa.Column("name", sa.String(length=255), nullable=False, comment="Unique connector name"),
        sa.Column("provider", sa.String(length=50), nullable=False, comment="External service provider"),
        sa.Column(
            "config",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"),
            nullable=False,
            comment="Non-sensitive provider configuration",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "credentials_ciphertext",
            sa.LargeBinary(),
            nullable=False,
            comment="AES-GCM encrypted credential JSON including the authentication tag",
        ),
        sa.Column(
            "credentials_nonce",
            sa.LargeBinary(),
            nullable=False,
            comment="Unique 12-byte AES-GCM nonce",
        ),
        sa.Column(
            "credential_key_version",
            sa.String(length=255),
            nullable=False,
            comment="Secret Manager version used to encrypt credentials",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_connectors_provider"), "connectors", ["provider"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_connectors_provider"), table_name="connectors")
    op.drop_table("connectors")
