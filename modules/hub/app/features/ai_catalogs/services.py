from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from app.features.ai_catalogs.models import AICatalog, AICatalogState
from app.features.ai_catalogs.repos import AICatalogRepository
from app.features.ai_catalogs.schemas import SetAvailabilityRequest, UpdateRefreshPolicyRequest
from app.features.project_management.pipeline_runs.models import PipelineRun
from app.features.project_management.projects.services import ProjectError
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

SHORT_REFRESH_FAILURE_LIMIT = 2


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AICatalogService:
    def __init__(self, repo: Annotated[AICatalogRepository, Depends()]) -> None:
        self.repo = repo

    @staticmethod
    def effective_concurrency(catalog: AICatalog) -> int:
        return 1 if catalog.availability_state == AICatalogState.PROBE else catalog.configured_concurrency

    @staticmethod
    def _usage_window(catalog: AICatalog) -> timedelta:
        # A long-cycle-only plan has no short window, so its usage window is the long cycle.
        minutes = (
            catalog.short_refresh_cycle_minutes if catalog.short_refresh_enabled else catalog.long_refresh_cycle_minutes
        )
        return timedelta(minutes=minutes)

    @staticmethod
    def _hold_state(catalog: AICatalog) -> AICatalogState:
        # A disabled catalog keeps its hold time so re-enabling cannot dispatch before the reset.
        return AICatalogState.QUOTA_BLOCKED if catalog.enabled else AICatalogState.DISABLED

    @staticmethod
    def _settle_probe(catalog: AICatalog, now: datetime) -> None:
        """Finish a delivered probe whose window passed without a quota event.

        Derived from persisted fields, so a transition discarded by a rejected admission is re-applied later.
        """
        if (
            catalog.availability_state == AICatalogState.PROBE
            and catalog.probe_started_at is not None
            and now - _utc(catalog.probe_started_at) >= timedelta(minutes=catalog.probe_window_minutes)
        ):
            catalog.availability_state = AICatalogState.NORMAL
            catalog.probe_started_at = None
            catalog.available_at = None
            catalog.short_refresh_failure_count = 0
            catalog.availability_note = "Recovery probe completed; normal catalog concurrency restored"
            catalog.revision += 1

    async def request_dispatch(self, session: AsyncSession, catalog_id: UUID, run_id: UUID, now: datetime) -> AICatalog:
        """Catalog gateway admission: block, probe, and capacity are decided here."""
        catalog = await self.repo.get(session, catalog_id, lock=True)
        if catalog is None:
            raise ProjectError(409, "AI catalog was removed")
        if not catalog.enabled or catalog.availability_state in (
            AICatalogState.DISABLED,
            AICatalogState.UNKNOWN,
        ):
            raise ProjectError(409, "AI catalog is unavailable")
        if catalog.availability_state == AICatalogState.QUOTA_BLOCKED:
            if catalog.available_at is None or _utc(catalog.available_at) > now:
                raise ProjectError(409, "AI catalog is quota-blocked; wait for its refresh time")
            catalog.availability_state = AICatalogState.PROBE
            # The observation window and the next usage window both start when the probe is delivered.
            catalog.probe_started_at = None
            catalog.usage_window_started_at = None
            catalog.last_refreshed_at = _utc(catalog.available_at)
            catalog.revision += 1
        else:
            self._settle_probe(catalog, now)
        if await self.repo.active_run_count(session, catalog_id, run_id) >= self.effective_concurrency(catalog):
            raise ProjectError(409, "AI catalog has reached its concurrency limit")
        await session.flush()
        return catalog

    async def record_dispatch_delivered(self, session: AsyncSession, catalog_id: UUID, posted_at: datetime) -> None:
        """Track the first task of the provider usage window and start a pending probe window."""
        catalog = await self.repo.get(session, catalog_id, lock=True)
        if catalog is None:
            return
        posted_at = _utc(posted_at)
        if catalog.last_refreshed_at is not None and posted_at < _utc(catalog.last_refreshed_at):
            # A reconciled mention posted before the latest hold ended or was cleared belongs to the old window;
            # it can neither anchor the next window nor stand in for the probe.
            return
        changed = False
        window_started_at = catalog.usage_window_started_at
        if window_started_at is None or posted_at >= _utc(window_started_at) + self._usage_window(catalog):
            # The previous window has reset, so this delivery is the first task of a new one.
            catalog.usage_window_started_at = posted_at
            changed = True
        if catalog.availability_state == AICatalogState.PROBE and catalog.probe_started_at is None:
            catalog.probe_started_at = posted_at
            changed = True
        if changed:
            catalog.revision += 1
            await session.flush()

    async def require_dispatchable(self, session: AsyncSession, catalog_id: UUID, now: datetime) -> AICatalog:
        catalog = await self.repo.get(session, catalog_id, lock=True)
        if catalog is None or not catalog.enabled:
            raise ProjectError(409, "AI catalog is unavailable")
        if catalog.availability_state == AICatalogState.QUOTA_BLOCKED and (
            catalog.available_at is None or _utc(catalog.available_at) > now
        ):
            raise ProjectError(409, "AI catalog is quota-blocked; wait for its refresh time")
        return catalog

    async def set_availability(
        self, session: AsyncSession, key: str, request: SetAvailabilityRequest, now: datetime
    ) -> AICatalog:
        catalog = await self.repo.get_by_key(session, key, lock=True)
        if catalog is None:
            raise ProjectError(404, "AI catalog not found")
        available_at = _utc(request.available_at)
        if available_at <= now:
            raise ProjectError(422, "Availability time must be in the future")
        catalog.availability_state = self._hold_state(catalog)
        catalog.available_at = available_at
        catalog.availability_source = request.source
        catalog.availability_note = request.note
        catalog.availability_updated_at = now
        catalog.probe_started_at = None
        catalog.revision += 1
        await session.flush()
        return catalog

    async def clear_availability(self, session: AsyncSession, key: str, now: datetime) -> AICatalog:
        catalog = await self.repo.get_by_key(session, key, lock=True)
        if catalog is None:
            raise ProjectError(404, "AI catalog not found")
        catalog.availability_state = AICatalogState.NORMAL if catalog.enabled else AICatalogState.DISABLED
        catalog.available_at = None
        catalog.availability_source = "manual"
        catalog.availability_note = None
        catalog.availability_updated_at = now
        catalog.probe_started_at = None
        # The operator reports a reset: older quota evidence is spent and the next delivery opens a new window.
        catalog.last_refreshed_at = now
        catalog.usage_window_started_at = None
        catalog.revision += 1
        await session.flush()
        return catalog

    async def set_enabled(self, session: AsyncSession, key: str, enabled: bool, now: datetime) -> AICatalog:
        catalog = await self.repo.get_by_key(session, key, lock=True)
        if catalog is None:
            raise ProjectError(404, "AI catalog not found")
        catalog.enabled = enabled
        if not enabled:
            catalog.availability_state = AICatalogState.DISABLED
        elif catalog.available_at is not None:
            # A pending hold survives re-enabling; an expired one resumes through a recovery probe.
            catalog.availability_state = AICatalogState.QUOTA_BLOCKED
        else:
            catalog.availability_state = AICatalogState.NORMAL
        catalog.probe_started_at = None
        catalog.availability_source = "manual"
        catalog.availability_updated_at = now
        catalog.revision += 1
        await session.flush()
        return catalog

    async def update_refresh_policy(
        self, session: AsyncSession, key: str, request: UpdateRefreshPolicyRequest
    ) -> AICatalog:
        catalog = await self.repo.get_by_key(session, key, lock=True)
        if catalog is None:
            raise ProjectError(404, "AI catalog not found")
        catalog.short_refresh_enabled = request.short_refresh_enabled
        catalog.short_refresh_cycle_minutes = request.short_refresh_cycle_minutes
        catalog.long_refresh_cycle_minutes = request.long_refresh_cycle_minutes
        catalog.revision += 1
        await session.flush()
        return catalog

    async def record_quota_event(self, session: AsyncSession, run: PipelineRun, observed_at: datetime) -> AICatalog:
        """Apply the catalog's refresh-cycle policy after a quota observation."""
        catalog = await self.repo.get(session, run.ai_catalog_id, lock=True)
        if catalog is None:
            raise ProjectError(409, "AI catalog was removed")
        now = datetime.now(UTC)
        observed_at = _utc(observed_at)
        run.quota_block_count += 1
        self._settle_probe(catalog, observed_at)
        covered_until = catalog.available_at or catalog.last_refreshed_at
        if covered_until is not None and observed_at < _utc(covered_until):
            # Evidence from before the current hold or latest refresh is already accounted for: it must not
            # consume another short retry or move a verified hold earlier.
            await session.flush()
            return catalog
        use_short_cycle = (
            catalog.short_refresh_enabled and catalog.short_refresh_failure_count < SHORT_REFRESH_FAILURE_LIMIT
        )
        if use_short_cycle:
            cycle_minutes = catalog.short_refresh_cycle_minutes
            catalog.short_refresh_failure_count += 1
            cycle_name = "short"
        else:
            cycle_minutes = catalog.long_refresh_cycle_minutes
            cycle_name = "long"
        # Codex resets a usage window a fixed time after its first task. Without a known start inside the
        # current window, the observation is the latest possible start, which never releases the hold early.
        refresh_anchor = observed_at
        if catalog.usage_window_started_at is not None:
            window_started_at = _utc(catalog.usage_window_started_at)
            if window_started_at <= observed_at < window_started_at + self._usage_window(catalog):
                refresh_anchor = window_started_at
        catalog.available_at = refresh_anchor + timedelta(minutes=cycle_minutes + catalog.refresh_jitter_minutes)
        catalog.availability_source = f"quota-{cycle_name}-cycle"
        catalog.availability_state = self._hold_state(catalog)
        catalog.probe_started_at = None
        catalog.availability_note = (
            f"Codex reported a usage limit; waiting for the {cycle_name} cycle from the window's first task"
        )
        catalog.availability_updated_at = now
        catalog.revision += 1
        await session.flush()
        return catalog
