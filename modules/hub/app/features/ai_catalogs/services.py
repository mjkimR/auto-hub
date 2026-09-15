from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from app.features.ai_catalogs.models import AICatalog, AICatalogKind, AICatalogSession, AICatalogState
from app.features.ai_catalogs.policies.base import hold_state, utc
from app.features.ai_catalogs.policies.registry import find_quota_policy, quota_policy_for
from app.features.ai_catalogs.repos import AICatalogRepository
from app.features.ai_catalogs.schemas import SetAvailabilityRequest, UpdatePolicyConfigRequest
from app.features.configuration.connectors.models import Connector
from app.features.project_management.projects.services import ProjectError
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Kinds whose provider the hub calls directly: they hold their own connector and track provider sessions.
CATALOG_CONNECTOR_PROVIDERS: dict[str, str] = {AICatalogKind.JULES: "jules"}


@dataclass(frozen=True)
class Admission:
    catalog: AICatalog
    rejection: str | None = None


def _dispatch_rejection(catalog: AICatalog, now: datetime) -> str | None:
    """Gateway checks every kind shares, run before its policy; ``AICatalogRepository.admits_dispatch`` mirrors them."""
    if not catalog.enabled or catalog.availability_state in (AICatalogState.DISABLED, AICatalogState.UNKNOWN):
        return "AI catalog is unavailable"
    if catalog.availability_state == AICatalogState.QUOTA_BLOCKED and (
        catalog.available_at is None or utc(catalog.available_at) > now
    ):
        return "AI catalog is quota-blocked; wait for its refresh time"
    return None


class AICatalogService:
    def __init__(self, repo: Annotated[AICatalogRepository, Depends()]) -> None:
        self.repo = repo

    @staticmethod
    def effective_concurrency(catalog: AICatalog) -> int:
        # A kind without a quota policy can never be admitted, so it has no capacity to show.
        policy = find_quota_policy(catalog)
        return 0 if policy is None else policy.effective_concurrency(catalog)

    async def request_dispatch(
        self, session: AsyncSession, catalog_id: UUID, run_id: UUID | None, dispatch_key: str, now: datetime
    ) -> Admission:
        """Catalog gateway admission: shared checks and capacity are decided here, quota by the kind's policy.

        A rejection is returned rather than raised, so the caller can commit what the policy recorded while deciding.
        Admitted work enters the dispatch ledger once under ``dispatch_key``; its retries keep that entry.
        """
        catalog = await self.repo.get(session, catalog_id, lock=True)
        if catalog is None:
            raise ProjectError(409, "AI catalog was removed")
        if (rejection := _dispatch_rejection(catalog, now)) is not None:
            return Admission(catalog, rejection)
        policy = quota_policy_for(catalog)
        rejection = await policy.admit(session, catalog, dispatch_key, now)
        if rejection is None:
            active = await self.repo.active_dispatch_count(session, catalog_id, run_id)
            if active >= policy.effective_concurrency(catalog):
                rejection = "AI catalog has reached its concurrency limit"
        if rejection is None:
            await self.repo.reserve_dispatch(session, catalog_id, dispatch_key, now)
        await session.flush()
        return Admission(catalog, rejection)

    async def record_dispatch_delivered(self, session: AsyncSession, catalog_id: UUID, posted_at: datetime) -> None:
        catalog = await self.repo.get(session, catalog_id, lock=True)
        if catalog is None:
            return
        await quota_policy_for(catalog).on_delivered(session, catalog, utc(posted_at))
        await session.flush()

    async def require_dispatchable(self, session: AsyncSession, catalog_id: UUID, now: datetime) -> AICatalog:
        catalog = await self.repo.get(session, catalog_id, lock=True)
        if catalog is None:
            raise ProjectError(409, "AI catalog is unavailable")
        if (rejection := _dispatch_rejection(catalog, now)) is not None:
            raise ProjectError(409, rejection)
        return catalog

    async def set_availability(
        self, session: AsyncSession, key: str, request: SetAvailabilityRequest, now: datetime
    ) -> AICatalog:
        catalog = await self._get_for_update(session, key)
        available_at = utc(request.available_at)
        if available_at <= now:
            raise ProjectError(422, "Availability time must be in the future")
        catalog.availability_state = hold_state(catalog)
        catalog.available_at = available_at
        catalog.availability_source = request.source
        catalog.availability_note = request.note
        catalog.availability_updated_at = now
        await self._override_policy_state(session, catalog, now)
        catalog.revision += 1
        await session.flush()
        return catalog

    async def clear_availability(self, session: AsyncSession, key: str, now: datetime) -> AICatalog:
        catalog = await self._get_for_update(session, key)
        catalog.availability_state = AICatalogState.NORMAL if catalog.enabled else AICatalogState.DISABLED
        catalog.available_at = None
        catalog.availability_source = "manual"
        catalog.availability_note = None
        catalog.availability_updated_at = now
        if (policy := find_quota_policy(catalog)) is not None:
            await policy.on_hold_cleared(session, catalog, now)
        catalog.revision += 1
        await session.flush()
        return catalog

    async def set_enabled(self, session: AsyncSession, key: str, enabled: bool, now: datetime) -> AICatalog:
        catalog = await self._get_for_update(session, key)
        catalog.enabled = enabled
        if not enabled:
            catalog.availability_state = AICatalogState.DISABLED
        elif catalog.available_at is not None:
            # A pending hold survives re-enabling; an expired one resumes through the kind's recovery.
            catalog.availability_state = AICatalogState.QUOTA_BLOCKED
        else:
            catalog.availability_state = AICatalogState.NORMAL
        catalog.availability_source = "manual"
        catalog.availability_updated_at = now
        await self._override_policy_state(session, catalog, now)
        catalog.revision += 1
        await session.flush()
        return catalog

    async def update_policy_config(
        self, session: AsyncSession, key: str, request: UpdatePolicyConfigRequest
    ) -> AICatalog:
        catalog = await self._get_for_update(session, key)
        catalog.policy_config = quota_policy_for(catalog).validate_config(request.policy_config)
        catalog.revision += 1
        await session.flush()
        return catalog

    async def set_connector(self, session: AsyncSession, key: str, connector_id: UUID | None) -> AICatalog:
        catalog = await self._get_for_update(session, key)
        provider = CATALOG_CONNECTOR_PROVIDERS.get(catalog.kind)
        if provider is None:
            raise ProjectError(422, "This catalog kind uses each project's GitHub connection, not its own connector")
        if connector_id is not None:
            connector = await session.get(Connector, connector_id)
            if connector is None or connector.provider != provider:
                raise ProjectError(422, f"Select a {provider} connector for this catalog")
        catalog.connector_id = connector_id
        catalog.revision += 1
        await session.flush()
        return catalog

    async def list_sessions(
        self, session: AsyncSession, key: str, *, offset: int, limit: int
    ) -> tuple[Sequence[AICatalogSession], int]:
        catalog = await self.repo.get_by_key(session, key)
        if catalog is None:
            raise ProjectError(404, "AI catalog not found")
        return await self.repo.list_sessions(session, catalog.id, offset=offset, limit=limit)

    async def record_quota_event(self, session: AsyncSession, catalog_id: UUID, observed_at: datetime) -> AICatalog:
        catalog = await self.repo.get(session, catalog_id, lock=True)
        if catalog is None:
            raise ProjectError(409, "AI catalog was removed")
        await quota_policy_for(catalog).on_quota_signal(session, catalog, utc(observed_at), datetime.now(UTC))
        await session.flush()
        return catalog

    async def _get_for_update(self, session: AsyncSession, key: str) -> AICatalog:
        catalog = await self.repo.get_by_key(session, key, lock=True)
        if catalog is None:
            raise ProjectError(404, "AI catalog not found")
        return catalog

    @staticmethod
    async def _override_policy_state(session: AsyncSession, catalog: AICatalog, now: datetime) -> None:
        # A kind without a policy has no recovery state to drop, and must still be switchable.
        if (policy := find_quota_policy(catalog)) is not None:
            await policy.on_availability_override(session, catalog, now)
