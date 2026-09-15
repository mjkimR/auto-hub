from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import UUID

from app.features.ai_catalogs.models import (
    SESSION_TERMINAL_STATES,
    AICatalog,
    AICatalogDispatch,
    AICatalogSession,
    AICatalogState,
)
from app.features.project_management.pipeline_runs.models import (
    ExecutionAttempt,
    ExecutionAttemptState,
    PipelineRun,
    PipelineRunState,
)
from sqlalchemy import ColumnElement, and_, delete, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# Quota windows span at most a day; older ledger entries are only history.
DISPATCH_LEDGER_RETENTION = timedelta(days=30)


class AICatalogRepository:
    @staticmethod
    def admits_dispatch(ready_at: datetime | None) -> ColumnElement[bool]:
        """SQL form of the gateway checks every kind shares; the kind's policy still decides at admission.

        Keep in step with ``services._dispatch_rejection``. Without ``ready_at`` every hold excludes the catalog.
        """
        hold = AICatalog.availability_state == AICatalogState.QUOTA_BLOCKED
        if ready_at is not None:
            hold = hold & or_(AICatalog.available_at.is_(None), AICatalog.available_at > ready_at)
        return and_(
            AICatalog.enabled.is_(True),
            AICatalog.availability_state.not_in((AICatalogState.DISABLED, AICatalogState.UNKNOWN)),
            not_(hold),
        )

    async def list(self, session: AsyncSession) -> list[AICatalog]:
        return list((await session.scalars(select(AICatalog).order_by(AICatalog.key))).all())

    async def get(self, session: AsyncSession, catalog_id: UUID, *, lock: bool = False) -> AICatalog | None:
        return await session.get(AICatalog, catalog_id, with_for_update=lock)

    async def get_by_key(self, session: AsyncSession, key: str, *, lock: bool = False) -> AICatalog | None:
        return (
            await session.scalars(
                select(AICatalog).where(AICatalog.key == key).with_for_update()
                if lock
                else select(AICatalog).where(AICatalog.key == key)
            )
        ).one_or_none()

    async def dispatch_times_since(
        self,
        session: AsyncSession,
        catalog_id: UUID,
        since: datetime,
        *,
        exclude_dispatch_key: str | None = None,
    ) -> Sequence[datetime]:
        """Admission times inside a quota window, oldest first."""
        filters = [AICatalogDispatch.ai_catalog_id == catalog_id, AICatalogDispatch.admitted_at >= since]
        if exclude_dispatch_key is not None:
            filters.append(AICatalogDispatch.dispatch_key != exclude_dispatch_key)
        rows = await session.scalars(
            select(AICatalogDispatch.admitted_at).where(*filters).order_by(AICatalogDispatch.admitted_at)
        )
        return rows.all()

    async def reserve_dispatch(
        self, session: AsyncSession, catalog_id: UUID, dispatch_key: str, admitted_at: datetime
    ) -> None:
        """Count a unit of work once: a retry keeps its first admission. Expired history is pruned here."""
        await session.execute(
            delete(AICatalogDispatch).where(
                AICatalogDispatch.ai_catalog_id == catalog_id,
                AICatalogDispatch.admitted_at < admitted_at - DISPATCH_LEDGER_RETENTION,
            )
        )
        existing = await session.scalar(
            select(AICatalogDispatch.id).where(AICatalogDispatch.dispatch_key == dispatch_key)
        )
        if existing is None:
            session.add(AICatalogDispatch(ai_catalog_id=catalog_id, dispatch_key=dispatch_key, admitted_at=admitted_at))

    async def held_run_count(self, session: AsyncSession, catalog_id: UUID, now: datetime) -> int:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(PipelineRun)
                .where(
                    PipelineRun.ai_catalog_id == catalog_id,
                    PipelineRun.state.in_(
                        (PipelineRunState.QUEUED, PipelineRunState.DISPATCHING, PipelineRunState.IMPLEMENTING)
                    ),
                )
            )
            or 0
        )

    async def active_dispatch_count(
        self, session: AsyncSession, catalog_id: UUID, exclude_run_id: UUID | None = None
    ) -> int:
        """Count work holding catalog capacity: pipeline runs with a delivered or admitted mention, and sessions.

        A DISPATCHING run still waiting for admission holds nothing, so waiting runs cannot block each other.
        """
        admitted = (
            select(ExecutionAttempt.id)
            .where(
                ExecutionAttempt.pipeline_run_id == PipelineRun.id,
                ExecutionAttempt.state == ExecutionAttemptState.DISPATCHING,
            )
            .exists()
        )
        filters = [
            PipelineRun.ai_catalog_id == catalog_id,
            or_(
                PipelineRun.state == PipelineRunState.IMPLEMENTING,
                (PipelineRun.state == PipelineRunState.DISPATCHING) & admitted,
            ),
        ]
        if exclude_run_id is not None:
            filters.append(PipelineRun.id != exclude_run_id)
        runs = await session.scalar(select(func.count()).select_from(PipelineRun).where(*filters))
        return int(runs or 0) + await self.open_session_count(session, catalog_id)

    async def open_session_count(self, session: AsyncSession, catalog_id: UUID) -> int:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(AICatalogSession)
                .where(
                    AICatalogSession.ai_catalog_id == catalog_id,
                    AICatalogSession.state.not_in(SESSION_TERMINAL_STATES),
                )
            )
            or 0
        )

    async def list_unfinished_sessions(self, session: AsyncSession, catalog_id: UUID) -> Sequence[AICatalogSession]:
        rows = await session.scalars(
            select(AICatalogSession)
            .where(
                AICatalogSession.ai_catalog_id == catalog_id,
                AICatalogSession.state.not_in(SESSION_TERMINAL_STATES),
            )
            .order_by(AICatalogSession.created_at)
        )
        return rows.all()

    async def list_sessions(
        self, session: AsyncSession, catalog_id: UUID, *, offset: int, limit: int
    ) -> tuple[Sequence[AICatalogSession], int]:
        """One page of sessions, most recent first, with the catalog's total session count."""
        rows = await session.scalars(
            select(AICatalogSession)
            .where(AICatalogSession.ai_catalog_id == catalog_id)
            .order_by(AICatalogSession.created_at.desc(), AICatalogSession.id)
            .offset(offset)
            .limit(limit)
        )
        total = await session.scalar(
            select(func.count()).select_from(AICatalogSession).where(AICatalogSession.ai_catalog_id == catalog_id)
        )
        return rows.all(), int(total or 0)
