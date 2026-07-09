from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy.orm import Mapped, mapped_column


class SystemConfig(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "system_configs"
    name: Mapped[str] = mapped_column(unique=True, comment="Unique key identifying the system config entry")
    data: Mapped[dict] = mapped_column(
        JSON_VARIANT, nullable=False, default={}, comment="Arbitrary JSON data associated with this system config"
    )
