from datetime import datetime

from app.features.ai_catalogs.models import AICatalogKind, AICatalogState
from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class AICatalogRead(UUIDSchemaMixin, TimestampSchemaMixin):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    kind: AICatalogKind
    adapter: str
    enabled: bool
    availability_state: AICatalogState
    available_at: datetime | None
    availability_source: str | None
    availability_updated_at: datetime | None
    availability_note: str | None
    configured_concurrency: int
    effective_concurrency: int = 0
    probe_started_at: datetime | None
    probe_window_minutes: int
    short_refresh_enabled: bool
    short_refresh_cycle_minutes: int
    long_refresh_cycle_minutes: int
    refresh_jitter_minutes: int
    short_refresh_failure_count: int
    last_refreshed_at: datetime | None
    usage_window_started_at: datetime | None
    revision: int
    held_run_count: int = 0
    active_run_count: int = 0


class AICatalogList(BaseModel):
    items: list[AICatalogRead]


class SetAvailabilityRequest(BaseModel):
    available_at: datetime
    note: str | None = Field(default=None, max_length=500)
    source: str = Field(default="manual", pattern="^(manual|local-codex-cli)$")


class SetEnabledRequest(BaseModel):
    enabled: bool


class UpdateRefreshPolicyRequest(BaseModel):
    short_refresh_enabled: bool
    short_refresh_cycle_minutes: int = Field(ge=1, le=43_200)
    long_refresh_cycle_minutes: int = Field(ge=1, le=525_600)
