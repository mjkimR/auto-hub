from enum import StrEnum

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ConnectorProvider(StrEnum):
    GITHUB = "github"
    # Credentials hold the Jules API key as ``token``.
    JULES = "jules"
    # Offered by the connectors UI; no backend feature reads Linear credentials yet.
    LINEAR = "linear"


class ConnectorBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider: ConnectorProvider
    config: dict[str, JsonValue] = Field(default_factory=dict)
    enabled: bool = True


class ConnectorCreate(ConnectorBase):
    credentials: dict[str, JsonValue] = Field(min_length=1)


class ConnectorPut(ConnectorBase):
    credentials: dict[str, JsonValue] = Field(min_length=1)


class ConnectorPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: dict[str, JsonValue] | None = None
    enabled: bool | None = None
    credentials: dict[str, JsonValue] = Field(default_factory=dict, min_length=1)


class ConnectorRead(UUIDSchemaMixin, TimestampSchemaMixin, ConnectorBase):
    model_config = ConfigDict(from_attributes=True)

    has_credentials: bool
