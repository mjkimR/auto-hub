from datetime import datetime
from uuid import UUID

from app.features.ai_catalogs.models import AICatalogKind, AICatalogState
from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class AICatalogRead(UUIDSchemaMixin, TimestampSchemaMixin):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    kind: AICatalogKind
    adapter: str
    connector_id: UUID | None
    enabled: bool
    availability_state: AICatalogState
    available_at: datetime | None
    availability_source: str | None
    availability_updated_at: datetime | None
    availability_note: str | None
    configured_concurrency: int
    effective_concurrency: int = 0
    refresh_jitter_minutes: int
    policy_config: dict = Field(default_factory=dict)
    policy_state: dict = Field(default_factory=dict)
    revision: int
    held_run_count: int = 0
    active_dispatch_count: int = 0
    open_session_count: int = 0
    connector_provider: str | None = Field(
        default=None, description="Connector provider the catalog authenticates with; set for kinds with sessions"
    )
    pipeline_delivery: bool = Field(
        default=False, description="Whether the catalog's adapter can deliver pull request pipeline work"
    )


class AICatalogList(BaseModel):
    items: list[AICatalogRead]


class AICatalogSessionRead(UUIDSchemaMixin, TimestampSchemaMixin):
    model_config = ConfigDict(from_attributes=True)

    schedule_config_id: UUID | None
    title: str
    state: str
    external_name: str | None
    url: str | None
    pull_request_url: str | None
    failure_detail: str | None
    observed_at: datetime | None


class AICatalogSessionList(BaseModel):
    items: list[AICatalogSessionRead]
    total_count: int


class SetAvailabilityRequest(BaseModel):
    available_at: datetime
    note: str | None = Field(default=None, max_length=500)
    source: str = Field(default="manual", pattern="^(manual|local-codex-cli)$")


class SetEnabledRequest(BaseModel):
    enabled: bool


class UpdatePolicyConfigRequest(BaseModel):
    """Kind-specific quota settings; the catalog's quota policy validates and normalizes them."""

    policy_config: dict


class SetConnectorRequest(BaseModel):
    connector_id: UUID | None
