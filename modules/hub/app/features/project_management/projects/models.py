from uuid import UUID

from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class Project(Base, UUIDMixin, TimestampMixin):
    """A workspace owned by Hub, with optional provider-specific connections."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255))
    github_repository: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    github_connector_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("connectors.id", ondelete="RESTRICT"), nullable=True
    )
    # The AI catalog that receives this project's pull request work; empty selects the seeded Codex catalog.
    ai_catalog_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai_catalogs.id", ondelete="RESTRICT"), nullable=True)
    verification: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    automation: Mapped[dict] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)
    revision: Mapped[int] = mapped_column(default=1)
    template_id: Mapped[str | None] = mapped_column(String(50))
    template_version: Mapped[str | None] = mapped_column(String(50))
    last_check: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)


# Kept as an import alias for extensions written against the pre-refactor model.
ProjectConnection = Project
