from datetime import datetime

from app.features.execution_providers.models import ExecutionProviderAvailability, ExecutionProviderKind
from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class ExecutionProviderRead(UUIDSchemaMixin, TimestampSchemaMixin):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    kind: ExecutionProviderKind
    adapter: str
    enabled: bool
    availability_state: ExecutionProviderAvailability
    available_at: datetime | None
    availability_source: str | None
    availability_updated_at: datetime | None
    availability_note: str | None
    configured_concurrency: int
    effective_concurrency: int = 0
    probe_started_at: datetime | None
    probe_window_minutes: int
    revision: int
    held_run_count: int = 0


class ExecutionProviderList(BaseModel):
    items: list[ExecutionProviderRead]


class SetAvailabilityRequest(BaseModel):
    available_at: datetime
    note: str | None = Field(default=None, max_length=500)
    source: str = Field(default="manual", pattern="^(manual|local-codex-cli)$")


class SetEnabledRequest(BaseModel):
    enabled: bool
