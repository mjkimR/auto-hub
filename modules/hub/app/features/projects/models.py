from uuid import UUID

from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class ProjectConnection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "project_connections"
    __table_args__ = (CheckConstraint("repository = lower(repository)", name="ck_project_repository_lowercase"),)

    name: Mapped[str] = mapped_column(String(255))
    repository: Mapped[str] = mapped_column(String(255), unique=True)
    linear_project_id: Mapped[UUID] = mapped_column(unique=True)
    github_connector_id: Mapped[UUID] = mapped_column(ForeignKey("connectors.id", ondelete="RESTRICT"))
    linear_connector_id: Mapped[UUID | None] = mapped_column(ForeignKey("connectors.id", ondelete="RESTRICT"))
    verification: Mapped[dict] = mapped_column(JSON_VARIANT)
    enabled: Mapped[bool] = mapped_column(default=True)
    revision: Mapped[int] = mapped_column(default=1)
    template_id: Mapped[str | None] = mapped_column(String(50))
    template_version: Mapped[str | None] = mapped_column(String(50))
    last_check: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
