from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import Boolean, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column


class Connector(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "connectors"

    name: Mapped[str] = mapped_column(String(255), unique=True, comment="Unique connector name")
    provider: Mapped[str] = mapped_column(String(50), index=True, comment="External service provider")
    config: Mapped[dict] = mapped_column(
        JSON_VARIANT,
        nullable=False,
        default=dict,
        comment="Non-sensitive provider configuration",
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    credentials_ciphertext: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="AES-GCM encrypted credential JSON including the authentication tag",
    )
    credentials_nonce: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="Unique 12-byte AES-GCM nonce",
    )
    credential_key_version: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Secret Manager version used to encrypt credentials",
    )

    @property
    def has_credentials(self) -> bool:
        return bool(self.credentials_ciphertext)
