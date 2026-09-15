from datetime import UTC, datetime
from typing import Protocol

from app.features.ai_catalogs.models import AICatalog, AICatalogState
from sqlalchemy.ext.asyncio import AsyncSession


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def hold_state(catalog: AICatalog) -> AICatalogState:
    # A disabled catalog keeps its hold time so re-enabling cannot dispatch before the reset.
    return AICatalogState.QUOTA_BLOCKED if catalog.enabled else AICatalogState.DISABLED


class QuotaPolicy(Protocol):
    """How one kind of provider plan consumes and recovers quota.

    The gateway service locks the catalog, rejects disabled catalogs and unexpired holds, checks capacity, and
    flushes. A policy only mutates the locked catalog, bumping its revision when it changes it.
    """

    def effective_concurrency(self, catalog: AICatalog) -> int: ...

    def validate_config(self, config: dict) -> dict:
        """Return the normalized ``policy_config`` for this kind; raise ProjectError(422) when it is invalid."""
        ...

    async def admit(self, session: AsyncSession, catalog: AICatalog, dispatch_key: str, now: datetime) -> str | None:
        """Apply recovery transitions before capacity is checked and return a rejection reason, if any.

        Runs only for an enabled catalog without an unexpired hold. Its transitions are committed even when the
        admission is rejected, so a policy can record a hold it has just reached. ``dispatch_key`` may already be
        in the dispatch ledger when work is retried; it must not be counted against itself.
        """
        ...

    async def on_delivered(self, session: AsyncSession, catalog: AICatalog, posted_at: datetime) -> None: ...

    async def on_quota_signal(
        self, session: AsyncSession, catalog: AICatalog, observed_at: datetime, now: datetime
    ) -> None: ...

    async def on_hold_cleared(self, session: AsyncSession, catalog: AICatalog, now: datetime) -> None: ...
