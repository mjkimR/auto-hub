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
            catalog.probe_started_at = now
            catalog.last_refreshed_at = _utc(catalog.available_at)
            catalog.revision += 1
        elif (
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
        if await self.repo.active_run_count(session, catalog_id, run_id) >= self.effective_concurrency(catalog):
            raise ProjectError(409, "AI catalog has reached its concurrency limit")
        await session.flush()
        return catalog

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
        catalog.availability_state = AICatalogState.QUOTA_BLOCKED
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
        catalog.revision += 1
        await session.flush()
        return catalog

    async def set_enabled(self, session: AsyncSession, key: str, enabled: bool, now: datetime) -> AICatalog:
        catalog = await self.repo.get_by_key(session, key, lock=True)
        if catalog is None:
            raise ProjectError(404, "AI catalog not found")
        catalog.enabled = enabled
        catalog.availability_state = AICatalogState.NORMAL if enabled else AICatalogState.DISABLED
        catalog.available_at = None if not enabled else catalog.available_at
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
        refresh_anchor = _utc(catalog.last_refreshed_at or observed_at)
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
        next_available_at = refresh_anchor + timedelta(minutes=cycle_minutes + catalog.refresh_jitter_minutes)
        if next_available_at <= now:
            next_available_at = now + timedelta(minutes=catalog.refresh_jitter_minutes)
        catalog.available_at = next_available_at
        catalog.availability_source = f"quota-{cycle_name}-cycle"
        run.quota_block_count += 1
        catalog.availability_state = AICatalogState.QUOTA_BLOCKED
        catalog.availability_note = (
            f"Codex reported a usage limit; waiting for the {cycle_name} refresh cycle plus safety jitter"
        )
        catalog.availability_updated_at = now
        catalog.revision += 1
        await session.flush()
        return catalog
