"""Move Codex usage-window state into policy_state, let projects select an AI catalog, and name delivery IDs generically.

- ``ai_catalogs.policy_state`` holds each kind's runtime quota state; the Codex usage-window columns move into it.
- ``projects.ai_catalog_id`` selects the catalog for a project's pull request work; empty keeps ``personal-codex``.
- ``execution_deliveries.comment_id`` and ``execution_replies.comment_id`` become ``external_id``: adapters store
  the provider's identifier there, which is a GitHub comment ID only for the Codex mention adapter.

Revision ID: d9e0f1a2b3c4
Revises: b8c9d0e1f2a3
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d9e0f1a2b3c4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_VARIANT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
TIMESTAMP_STATE = ("probe_started_at", "last_refreshed_at", "usage_window_started_at")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()


def _catalogs_with_state() -> sa.TableClause:
    return sa.table(
        "ai_catalogs",
        sa.column("id", sa.Uuid()),
        sa.column("kind", sa.String()),
        sa.column("policy_state", JSON_VARIANT),
        sa.column("probe_started_at", sa.DateTime(timezone=True)),
        sa.column("short_refresh_failure_count", sa.Integer()),
        sa.column("last_refreshed_at", sa.DateTime(timezone=True)),
        sa.column("usage_window_started_at", sa.DateTime(timezone=True)),
    )


def upgrade() -> None:
    op.add_column(
        "ai_catalogs",
        sa.Column("policy_state", JSON_VARIANT, server_default=sa.text("'{}'"), nullable=False),
    )
    catalogs = _catalogs_with_state()
    bind = op.get_bind()
    for row in bind.execute(sa.select(catalogs).where(catalogs.c.kind == "codex")).mappings().all():
        state = {name: _iso(row[name]) for name in TIMESTAMP_STATE}
        state["short_refresh_failure_count"] = int(row["short_refresh_failure_count"] or 0)
        bind.execute(catalogs.update().where(catalogs.c.id == row["id"]).values(policy_state=state))
    with op.batch_alter_table("ai_catalogs") as batch:
        batch.drop_column("probe_started_at")
        batch.drop_column("short_refresh_failure_count")
        batch.drop_column("last_refreshed_at")
        batch.drop_column("usage_window_started_at")

    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("ai_catalog_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_projects_ai_catalog_id", "ai_catalogs", ["ai_catalog_id"], ["id"], ondelete="RESTRICT"
        )

    with op.batch_alter_table("execution_deliveries") as batch:
        batch.alter_column(
            "comment_id", new_column_name="external_id", existing_type=sa.String(255), existing_nullable=True
        )
    with op.batch_alter_table("execution_replies") as batch:
        batch.alter_column(
            "comment_id", new_column_name="external_id", existing_type=sa.String(255), existing_nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table("execution_replies") as batch:
        batch.alter_column(
            "external_id", new_column_name="comment_id", existing_type=sa.String(255), existing_nullable=False
        )
    with op.batch_alter_table("execution_deliveries") as batch:
        batch.alter_column(
            "external_id", new_column_name="comment_id", existing_type=sa.String(255), existing_nullable=True
        )

    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("fk_projects_ai_catalog_id", type_="foreignkey")
        batch.drop_column("ai_catalog_id")

    with op.batch_alter_table("ai_catalogs") as batch:
        batch.add_column(sa.Column("probe_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("short_refresh_failure_count", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("usage_window_started_at", sa.DateTime(timezone=True), nullable=True))
    catalogs = _catalogs_with_state()
    bind = op.get_bind()
    for row in bind.execute(sa.select(catalogs.c.id, catalogs.c.policy_state)).mappings().all():
        state = row["policy_state"] or {}
        values = {
            name: datetime.fromisoformat(state[name]) if isinstance(state.get(name), str) else None
            for name in TIMESTAMP_STATE
        }
        values["short_refresh_failure_count"] = int(state.get("short_refresh_failure_count") or 0)
        bind.execute(catalogs.update().where(catalogs.c.id == row["id"]).values(**values))
    op.drop_column("ai_catalogs", "policy_state")
