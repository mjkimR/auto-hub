from datetime import datetime
from enum import StrEnum

from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class ExecutionProviderKind(StrEnum):
    CODEX = "codex"
    JULES = "jules"
    OPENAI_API = "openai-api"


class ExecutionProviderAvailability(StrEnum):
    NORMAL = "normal"
    QUOTA_BLOCKED = "quota_blocked"
    PROBE = "probe"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class ExecutionProvider(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "execution_providers"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    adapter: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    availability_state: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    availability_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    availability_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    availability_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    configured_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    probe_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    probe_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
