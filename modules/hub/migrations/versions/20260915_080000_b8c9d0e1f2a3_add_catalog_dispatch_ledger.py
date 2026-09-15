"""Generalize AI catalog quota: per-kind policy settings, a dispatch ledger, and tracked agent sessions.

- Codex refresh-cycle settings move from columns into ``policy_config``; usage-window state stays in columns.
- ``ai_catalog_dispatches`` counts each admitted delivery or session once, so daily task caps are enforced
  before a provider refuses work. Existing deliveries are not backfilled; Codex quota does not read the ledger.
- ``ai_catalog_sessions`` tracks provider sessions started outside the pull request pipeline (Jules).
- A Jules catalog is seeded with Jules Pro limits (100 tasks per rolling 24 hours, 15 concurrent); assign its
  connector before scheduling sessions.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_VARIANT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
PERSONAL_JULES_ID = UUID("00000000-0000-0000-0000-000000000002")
TIMESTAMPS = (
    ("created_at", sa.text("CURRENT_TIMESTAMP")),
    ("updated_at", sa.text("CURRENT_TIMESTAMP")),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=False)
        for name, default in TIMESTAMPS
    ]


def upgrade() -> None:
    op.add_column(
        "ai_catalogs",
        sa.Column("policy_config", JSON_VARIANT, server_default=sa.text("'{}'"), nullable=False),
    )
    op.add_column("ai_catalogs", sa.Column("connector_id", sa.Uuid(), nullable=True))

    catalogs = sa.table(
        "ai_catalogs",
        sa.column("id", sa.Uuid()),
        sa.column("kind", sa.String()),
        sa.column("policy_config", JSON_VARIANT),
        sa.column("short_refresh_enabled", sa.Boolean()),
        sa.column("short_refresh_cycle_minutes", sa.Integer()),
        sa.column("long_refresh_cycle_minutes", sa.Integer()),
        sa.column("probe_window_minutes", sa.Integer()),
    )
    bind = op.get_bind()
    for row in bind.execute(sa.select(catalogs).where(catalogs.c.kind == "codex")).mappings().all():
        config = {
            "short_refresh_enabled": bool(row["short_refresh_enabled"]),
            "short_refresh_cycle_minutes": int(row["short_refresh_cycle_minutes"]),
            "long_refresh_cycle_minutes": int(row["long_refresh_cycle_minutes"]),
            "probe_window_minutes": int(row["probe_window_minutes"]),
        }
        bind.execute(catalogs.update().where(catalogs.c.id == row["id"]).values(policy_config=config))

    with op.batch_alter_table("ai_catalogs") as batch:
        batch.drop_column("short_refresh_enabled")
        batch.drop_column("short_refresh_cycle_minutes")
        batch.drop_column("long_refresh_cycle_minutes")
        batch.drop_column("probe_window_minutes")
        batch.create_foreign_key(
            "fk_ai_catalogs_connector_id", "connectors", ["connector_id"], ["id"], ondelete="RESTRICT"
        )

    op.create_table(
        "ai_catalog_dispatches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ai_catalog_id", sa.Uuid(), nullable=False),
        sa.Column("dispatch_key", sa.String(200), nullable=False),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["ai_catalog_id"], ["ai_catalogs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dispatch_key"),
    )
    op.create_index(
        "ix_ai_catalog_dispatches_catalog_admitted",
        "ai_catalog_dispatches",
        ["ai_catalog_id", "admitted_at"],
        unique=False,
    )

    op.create_table(
        "ai_catalog_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ai_catalog_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_config_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("external_name", sa.String(255), nullable=True),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("pull_request_url", sa.String(2048), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["ai_catalog_id"], ["ai_catalogs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["schedule_config_id"], ["schedule_configs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_name"),
    )
    op.create_index("ix_ai_catalog_sessions_ai_catalog_id", "ai_catalog_sessions", ["ai_catalog_id"], unique=False)
    op.create_index(
        "ix_ai_catalog_sessions_schedule_config_id", "ai_catalog_sessions", ["schedule_config_id"], unique=False
    )
    op.create_index("ix_ai_catalog_sessions_state", "ai_catalog_sessions", ["state"], unique=False)

    seeds = sa.table(
        "ai_catalogs",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("kind", sa.String()),
        sa.column("adapter", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("availability_state", sa.String()),
        sa.column("configured_concurrency", sa.Integer()),
        sa.column("refresh_jitter_minutes", sa.Integer()),
        sa.column("short_refresh_failure_count", sa.Integer()),
        sa.column("policy_config", JSON_VARIANT),
        sa.column("revision", sa.Integer()),
    )
    op.bulk_insert(
        seeds,
        [
            {
                "id": PERSONAL_JULES_ID,
                "key": "personal-jules",
                "name": "Personal Jules",
                "kind": "jules",
                "adapter": "jules-api",
                "enabled": True,
                "availability_state": "normal",
                "configured_concurrency": 15,
                "refresh_jitter_minutes": 10,
                "short_refresh_failure_count": 0,
                "policy_config": {"daily_task_limit": 100, "window": "rolling", "timezone": "UTC"},
                "revision": 1,
            }
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_catalog_sessions_state", table_name="ai_catalog_sessions")
    op.drop_index("ix_ai_catalog_sessions_schedule_config_id", table_name="ai_catalog_sessions")
    op.drop_index("ix_ai_catalog_sessions_ai_catalog_id", table_name="ai_catalog_sessions")
    op.drop_table("ai_catalog_sessions")
    op.drop_index("ix_ai_catalog_dispatches_catalog_admitted", table_name="ai_catalog_dispatches")
    op.drop_table("ai_catalog_dispatches")

    catalogs = sa.table("ai_catalogs", sa.column("id", sa.Uuid()), sa.column("kind", sa.String()))
    op.execute(catalogs.delete().where(catalogs.c.kind == "jules"))
    with op.batch_alter_table("ai_catalogs") as batch:
        batch.drop_constraint("fk_ai_catalogs_connector_id", type_="foreignkey")
        batch.add_column(sa.Column("short_refresh_enabled", sa.Boolean(), server_default=sa.true(), nullable=False))
        batch.add_column(sa.Column("short_refresh_cycle_minutes", sa.Integer(), server_default="300", nullable=False))
        batch.add_column(sa.Column("long_refresh_cycle_minutes", sa.Integer(), server_default="10080", nullable=False))
        batch.add_column(sa.Column("probe_window_minutes", sa.Integer(), server_default="10", nullable=False))
        batch.drop_column("connector_id")
        batch.drop_column("policy_config")
