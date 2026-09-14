from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from app.features.execution_providers.models import ExecutionProvider, ExecutionProviderAvailability
from app.features.execution_providers.repos import ExecutionProviderRepository
from app.features.execution_providers.schemas import SetAvailabilityRequest
from app.features.project_management.pipeline_runs.models import PipelineRun, PipelineRunState
from app.features.project_management.projects.services import ProjectError
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

CODEX_QUOTA_FALLBACK = timedelta(hours=5, minutes=10)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ExecutionProviderService:
    def __init__(self, repo: Annotated[ExecutionProviderRepository, Depends()]) -> None:
        self.repo = repo

    @staticmethod
    def effective_concurrency(provider: ExecutionProvider) -> int:
        return (
            1 if provider.availability_state == ExecutionProviderAvailability.PROBE else provider.configured_concurrency
        )

    async def request_dispatch(
        self, session: AsyncSession, provider_id: UUID, run_id: UUID, now: datetime
    ) -> ExecutionProvider:
        """Catalog gateway admission: block, probe, and capacity are decided here."""
        provider = await self.repo.get(session, provider_id, lock=True)
        if provider is None:
            raise ProjectError(409, "AI catalog was removed")
        if not provider.enabled or provider.availability_state in (
            ExecutionProviderAvailability.DISABLED,
            ExecutionProviderAvailability.UNKNOWN,
        ):
            raise ProjectError(409, "AI catalog is unavailable")
        if provider.availability_state == ExecutionProviderAvailability.QUOTA_BLOCKED:
            if provider.available_at is None or _utc(provider.available_at) > now:
                raise ProjectError(409, "AI catalog is quota-blocked; wait for its refresh time")
            provider.availability_state = ExecutionProviderAvailability.PROBE
            provider.probe_started_at = now
            provider.revision += 1
        elif (
            provider.availability_state == ExecutionProviderAvailability.PROBE
            and provider.probe_started_at is not None
            and now - _utc(provider.probe_started_at) >= timedelta(minutes=provider.probe_window_minutes)
        ):
            provider.availability_state = ExecutionProviderAvailability.NORMAL
            provider.probe_started_at = None
            provider.available_at = None
            provider.availability_note = "Recovery probe completed; normal catalog concurrency restored"
            provider.revision += 1
        if await self.repo.active_run_count(session, provider_id, run_id) >= self.effective_concurrency(provider):
            raise ProjectError(409, "AI catalog has reached its concurrency limit")
        await session.flush()
        return provider

    async def require_dispatchable(self, session: AsyncSession, provider_id: UUID, now: datetime) -> ExecutionProvider:
        provider = await self.repo.get(session, provider_id, lock=True)
        if provider is None or not provider.enabled:
            raise ProjectError(409, "AI catalog is unavailable")
        if provider.availability_state == ExecutionProviderAvailability.QUOTA_BLOCKED and (
            provider.available_at is None or _utc(provider.available_at) > now
        ):
            raise ProjectError(409, "AI catalog is quota-blocked; wait for its refresh time")
        return provider

    async def set_availability(
        self, session: AsyncSession, key: str, request: SetAvailabilityRequest, now: datetime
    ) -> ExecutionProvider:
        provider = await self.repo.get_by_key(session, key, lock=True)
        if provider is None:
            raise ProjectError(404, "Execution provider not found")
        available_at = _utc(request.available_at)
        if available_at <= now:
            raise ProjectError(422, "Availability time must be in the future")
        provider.availability_state = ExecutionProviderAvailability.QUOTA_BLOCKED
        provider.available_at = available_at
        provider.availability_source = request.source
        provider.availability_note = request.note
        provider.availability_updated_at = now
        provider.probe_started_at = None
        provider.revision += 1
        await session.flush()
        return provider

    async def clear_availability(self, session: AsyncSession, key: str, now: datetime) -> ExecutionProvider:
        provider = await self.repo.get_by_key(session, key, lock=True)
        if provider is None:
            raise ProjectError(404, "Execution provider not found")
        provider.availability_state = (
            ExecutionProviderAvailability.NORMAL if provider.enabled else ExecutionProviderAvailability.DISABLED
        )
        provider.available_at = None
        provider.availability_source = "manual"
        provider.availability_note = None
        provider.availability_updated_at = now
        provider.probe_started_at = None
        provider.revision += 1
        await session.flush()
        return provider

    async def set_enabled(self, session: AsyncSession, key: str, enabled: bool, now: datetime) -> ExecutionProvider:
        provider = await self.repo.get_by_key(session, key, lock=True)
        if provider is None:
            raise ProjectError(404, "Execution provider not found")
        provider.enabled = enabled
        provider.availability_state = (
            ExecutionProviderAvailability.NORMAL if enabled else ExecutionProviderAvailability.DISABLED
        )
        provider.available_at = None if not enabled else provider.available_at
        provider.availability_source = "manual"
        provider.availability_updated_at = now
        provider.revision += 1
        await session.flush()
        return provider

    async def record_quota_event(
        self, session: AsyncSession, run: PipelineRun, observed_at: datetime
    ) -> ExecutionProvider:
        """The catalog owns both the global block and the per-task quota cap."""
        provider = await self.repo.get(session, run.execution_provider_id, lock=True)
        if provider is None:
            raise ProjectError(409, "Execution provider was removed")
        now = datetime.now(UTC)
        fallback = _utc(observed_at) + CODEX_QUOTA_FALLBACK
        if (
            provider.available_at is None
            or _utc(provider.available_at) <= now
            or _utc(provider.available_at) < fallback
        ):
            provider.available_at = fallback
            provider.availability_source = "quota-fallback"
        run.quota_block_count += 1
        if run.quota_block_count >= 2:
            run.state = PipelineRunState.BLOCKED
            run.pause_reason = "AI catalog blocked this task after two quota events"
        provider.availability_state = ExecutionProviderAvailability.QUOTA_BLOCKED
        provider.availability_note = "Codex reported a usage limit; waiting for the provider reset window"
        provider.availability_updated_at = now
        provider.revision += 1
        await session.flush()
        return provider
