from datetime import UTC, datetime, timedelta, tzinfo
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.features.ai_catalogs.models import AICatalog, AICatalogState
from app.features.ai_catalogs.policies.base import hold_state, utc
from app.features.ai_catalogs.repos import AICatalogRepository
from app.features.project_management.projects.services import ProjectError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

WINDOW = timedelta(days=1)
DAILY_LIMIT_REJECTION = "AI catalog has reached its daily task limit; wait for its refresh time"


def _zone(name: str) -> tzinfo:
    if name == "UTC":
        return UTC
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Unknown timezone '{name}'") from None


class DailyQuotaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_task_limit: int = Field(ge=1, le=10_000)
    # "rolling" counts the last 24 hours, as Jules documents for its daily limit; "calendar" resets at local
    # midnight in ``timezone`` for providers that reset by day.
    window: Literal["rolling", "calendar"] = "rolling"
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        _zone(value)
        return value


class DailyQuotaPolicy:
    """Plans that cap parallel tasks and tasks per day, both known to the hub before it dispatches.

    The day's count comes from the dispatch ledger, so reaching the cap records a hold instead of waiting for the
    provider to refuse a task. ``configured_concurrency`` is the parallel cap.
    """

    def __init__(self, repo: AICatalogRepository) -> None:
        self.repo = repo

    def effective_concurrency(self, catalog: AICatalog) -> int:
        return catalog.configured_concurrency

    def validate_config(self, config: dict) -> dict:
        try:
            return DailyQuotaConfig.model_validate(config).model_dump()
        except ValidationError as exc:
            raise ProjectError(422, f"Invalid daily quota policy: {exc.errors()[0]['msg']}") from None

    @staticmethod
    def _config(catalog: AICatalog) -> DailyQuotaConfig:
        try:
            return DailyQuotaConfig.model_validate(catalog.policy_config)
        except ValidationError:
            raise ProjectError(409, "AI catalog has no valid daily quota policy; configure it first") from None

    @staticmethod
    def _window_start(config: DailyQuotaConfig, now: datetime) -> datetime:
        if config.window == "rolling":
            return now - WINDOW
        local = now.astimezone(_zone(config.timezone))
        return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)

    def _next_room_at(
        self, catalog: AICatalog, config: DailyQuotaConfig, admitted: list[datetime], now: datetime
    ) -> datetime:
        if config.window == "calendar":
            # Adding a day to a zone-aware midnight keeps wall-clock time, so DST days still reset at midnight.
            midnight = self._window_start(config, now).astimezone(_zone(config.timezone))
            reset_at = (midnight + WINDOW).astimezone(UTC)
        else:
            # The window has room again once all but limit - 1 of its tasks have aged out.
            reset_at = admitted[len(admitted) - config.daily_task_limit] + WINDOW
        return reset_at + timedelta(minutes=catalog.refresh_jitter_minutes)

    @staticmethod
    def _hold(catalog: AICatalog, until: datetime, now: datetime, note: str) -> None:
        catalog.available_at = until
        catalog.availability_state = hold_state(catalog)
        catalog.availability_source = "daily-task-limit"
        catalog.availability_note = note
        catalog.availability_updated_at = now
        catalog.revision += 1

    async def admit(self, session: AsyncSession, catalog: AICatalog, dispatch_key: str, now: datetime) -> str | None:
        config = self._config(catalog)
        if catalog.availability_state == AICatalogState.QUOTA_BLOCKED:
            # The gateway admits only an expired hold; the ledger below decides whether the window has room again.
            catalog.availability_state = AICatalogState.NORMAL
            catalog.available_at = None
            catalog.availability_note = "Daily task window refreshed"
            catalog.revision += 1
        admitted = [
            utc(value)
            for value in await self.repo.dispatch_times_since(
                session, catalog.id, self._window_start(config, now), exclude_dispatch_key=dispatch_key
            )
        ]
        if len(admitted) < config.daily_task_limit:
            return None
        self._hold(
            catalog,
            self._next_room_at(catalog, config, admitted, now),
            now,
            f"Daily task limit of {config.daily_task_limit} reached; waiting for the window to refresh",
        )
        return DAILY_LIMIT_REJECTION

    async def on_delivered(self, session: AsyncSession, catalog: AICatalog, posted_at: datetime) -> None:
        return None

    async def on_quota_signal(
        self, session: AsyncSession, catalog: AICatalog, observed_at: datetime, now: datetime
    ) -> None:
        """The provider refused a task the ledger allowed, e.g. because tasks were started outside the hub."""
        if catalog.available_at is not None and observed_at < utc(catalog.available_at):
            return
        config = self._config(catalog)
        if config.window == "calendar":
            until = self._next_room_at(catalog, config, [], observed_at)
        else:
            # Tasks started elsewhere are invisible to the ledger, so wait a full window from the refusal.
            until = observed_at + WINDOW + timedelta(minutes=catalog.refresh_jitter_minutes)
        self._hold(catalog, until, now, "Provider reported its daily task limit; waiting for the window to refresh")

    async def on_hold_cleared(self, session: AsyncSession, catalog: AICatalog, now: datetime) -> None:
        return None

    async def on_availability_override(self, session: AsyncSession, catalog: AICatalog, now: datetime) -> None:
        return None
