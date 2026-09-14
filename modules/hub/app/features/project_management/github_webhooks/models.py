from datetime import datetime

from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class GitHubWebhookDelivery(Base, UUIDMixin, TimestampMixin):
    """Deduplication and processing audit without retaining GitHub payload content."""

    __tablename__ = "github_webhook_deliveries"

    delivery_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    repository: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="received")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
