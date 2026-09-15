from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class AICatalogKind(StrEnum):
    CODEX = "codex"
    JULES = "jules"


class AICatalogState(StrEnum):
    NORMAL = "normal"
    QUOTA_BLOCKED = "quota_blocked"
    PROBE = "probe"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class AICatalog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_catalogs"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    adapter: Mapped[str] = mapped_column(String(100), nullable=False)
    # Credentials for a provider the hub calls directly (the Jules API); pipeline adapters use the project's.
    connector_id: Mapped[UUID | None] = mapped_column(ForeignKey("connectors.id", ondelete="RESTRICT"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    availability_state: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    availability_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    availability_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    availability_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    configured_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    refresh_jitter_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    # Quota settings of the catalog's kind, validated by its quota policy.
    policy_config: Mapped[dict] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    # Runtime quota state of the catalog's kind, owned by its quota policy and replaced whole on change.
    policy_state: Mapped[dict] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AICatalogDispatch(Base, UUIDMixin, TimestampMixin):
    """One admitted unit of work, counted once against its catalog's task quota however often it is retried."""

    __tablename__ = "ai_catalog_dispatches"
    __table_args__ = (Index("ix_ai_catalog_dispatches_catalog_admitted", "ai_catalog_id", "admitted_at"),)

    ai_catalog_id: Mapped[UUID] = mapped_column(ForeignKey("ai_catalogs.id", ondelete="RESTRICT"), nullable=False)
    # "delivery:<id>" for a pipeline delivery, "session:<id>" for a tracked agent session.
    dispatch_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


SESSION_DISPATCHING = "dispatching"
SESSION_TERMINAL_STATES = ("completed", "failed")


class AICatalogSession(Base, UUIDMixin, TimestampMixin):
    """A provider session the hub started outside the pull request pipeline, tracked until it ends.

    Only state and links are kept; reports and changes stay with the provider or the pull requests it opens.
    """

    __tablename__ = "ai_catalog_sessions"

    ai_catalog_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_catalogs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    schedule_config_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("schedule_configs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Unique per session, so an unconfirmed create can be found again by title.
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # "dispatching" until the provider confirms the session, then its state in lower case.
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    external_name: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    pull_request_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
