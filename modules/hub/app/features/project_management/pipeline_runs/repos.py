from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.features.ai_catalogs.models import AICatalog
from app.features.ai_catalogs.repos import AICatalogRepository
from app.features.project_management.pipeline_runs.models import (
    ACTIVE_RUN_STATES,
    ExecutionAttempt,
    ExecutionAttemptState,
    ExecutionDelivery,
    ExecutionReply,
    PipelineRun,
    PipelineRunState,
)
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession


class PipelineRunRepository:
    async def get(self, session: AsyncSession, run_id: UUID, *, lock: bool = False) -> PipelineRun | None:
        return await session.get(PipelineRun, run_id, with_for_update=True if lock else None)

    async def get_leased(
        self,
        session: AsyncSession,
        run_id: UUID,
        *,
        owner: str,
        token: UUID,
        now: datetime,
    ) -> PipelineRun | None:
        return (
            await session.execute(
                select(PipelineRun)
                .where(
                    PipelineRun.id == run_id,
                    PipelineRun.lease_owner == owner,
                    PipelineRun.lease_token == token,
                    PipelineRun.lease_expires_at > now,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

    async def get_active_for_pull(
        self, session: AsyncSession, project_id: UUID, pull_number: int, *, lock: bool = False
    ) -> PipelineRun | None:
        stmt = select(PipelineRun).where(
            PipelineRun.project_id == project_id,
            PipelineRun.pull_number == pull_number,
            PipelineRun.state.in_(ACTIVE_RUN_STATES),
        )
        if lock:
            stmt = stmt.with_for_update()
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_active(
        self,
        session: AsyncSession,
        project_id: UUID,
        *,
        limit: int,
        ready_at: datetime | None = None,
        states: tuple[PipelineRunState, ...] | None = None,
    ) -> list[PipelineRun]:
        uncertain_delivery = (
            select(ExecutionAttempt.id)
            .where(
                ExecutionAttempt.pipeline_run_id == PipelineRun.id,
                ExecutionAttempt.state == ExecutionAttemptState.DISPATCHING,
            )
            .exists()
        )
        observing = PipelineRun.state.in_((PipelineRunState.IMPLEMENTING, PipelineRunState.AWAITING_CI))
        filters = [
            PipelineRun.project_id == project_id,
            PipelineRun.state.in_(ACTIVE_RUN_STATES),
            # Only dispatch needs catalog admission; CI, push, and quota-reply observation continue during a hold.
            or_(
                PipelineRun.state != PipelineRunState.DISPATCHING,
                uncertain_delivery,
                AICatalogRepository.admits_dispatch(ready_at),
            ),
        ]
        if states is not None:
            filters.append(PipelineRun.state.in_(states))
        if ready_at is not None:
            filters.extend(
                [
                    PipelineRun.state.in_(
                        (
                            PipelineRunState.QUEUED,
                            PipelineRunState.DISPATCHING,
                            PipelineRunState.IMPLEMENTING,
                            PipelineRunState.AWAITING_CI,
                        )
                    ),
                    or_(PipelineRun.next_action_at.is_(None), PipelineRun.next_action_at <= ready_at),
                    or_(PipelineRun.lease_token.is_(None), PipelineRun.lease_expires_at <= ready_at),
                ]
            )
        rows = await session.scalars(
            select(PipelineRun)
            .join(AICatalog, PipelineRun.ai_catalog_id == AICatalog.id)
            .where(*filters)
            .order_by(
                # Observe first to release capacity before admitting more work. Lease updates rotate
                # observed runs, so a batch smaller than the observing population still makes progress.
                case((observing, 0), (uncertain_delivery, 1), else_=2),
                case((or_(observing, uncertain_delivery), PipelineRun.updated_at), else_=PipelineRun.created_at),
                PipelineRun.next_action_at.nullsfirst(),
                PipelineRun.id,
            )
            .limit(limit)
        )
        return list(rows)

    async def list(
        self, session: AsyncSession, *, project_id: UUID | None, offset: int, limit: int
    ) -> tuple[list[PipelineRun], int]:
        filters = (PipelineRun.project_id == project_id,) if project_id else ()
        total = await session.scalar(select(func.count()).select_from(PipelineRun).where(*filters))
        rows = await session.scalars(
            select(PipelineRun)
            .where(*filters)
            .order_by(PipelineRun.created_at.desc(), PipelineRun.id)
            .offset(offset)
            .limit(limit)
        )
        return list(rows), total or 0

    async def create(self, session: AsyncSession, run: PipelineRun) -> PipelineRun:
        session.add(run)
        await session.flush()
        await session.refresh(run)
        return run

    async def active_attempt(self, session: AsyncSession, run_id: UUID) -> ExecutionAttempt | None:
        return (
            await session.scalars(
                select(ExecutionAttempt)
                .where(
                    ExecutionAttempt.pipeline_run_id == run_id,
                    ExecutionAttempt.state.in_(
                        (
                            ExecutionAttemptState.PLANNED,
                            ExecutionAttemptState.DISPATCHING,
                            ExecutionAttemptState.RUNNING,
                            ExecutionAttemptState.SUSPENDED,
                        )
                    ),
                )
                .order_by(ExecutionAttempt.attempt_number.desc())
                .limit(1)
            )
        ).one_or_none()

    async def next_attempt_number(self, session: AsyncSession, run_id: UUID) -> int:
        current = await session.scalar(
            select(func.max(ExecutionAttempt.attempt_number)).where(ExecutionAttempt.pipeline_run_id == run_id)
        )
        return (current or 0) + 1

    async def create_attempt(self, session: AsyncSession, attempt: ExecutionAttempt) -> ExecutionAttempt:
        session.add(attempt)
        await session.flush()
        await session.refresh(attempt)
        return attempt

    async def list_attempts(self, session: AsyncSession, run_id: UUID) -> list[ExecutionAttempt]:
        rows = await session.scalars(
            select(ExecutionAttempt)
            .where(ExecutionAttempt.pipeline_run_id == run_id)
            .order_by(ExecutionAttempt.attempt_number)
        )
        return list(rows)

    async def get_attempt(self, session: AsyncSession, attempt_id: UUID) -> ExecutionAttempt | None:
        return await session.get(ExecutionAttempt, attempt_id)

    async def latest_delivery(self, session: AsyncSession, attempt_id: UUID) -> ExecutionDelivery | None:
        return (
            await session.scalars(
                select(ExecutionDelivery)
                .where(ExecutionDelivery.execution_attempt_id == attempt_id)
                .order_by(ExecutionDelivery.delivery_number.desc())
                .limit(1)
            )
        ).one_or_none()

    async def create_delivery(self, session: AsyncSession, delivery: ExecutionDelivery) -> ExecutionDelivery:
        session.add(delivery)
        await session.flush()
        await session.refresh(delivery)
        return delivery

    async def list_deliveries(self, session: AsyncSession, attempt_id: UUID) -> list[ExecutionDelivery]:
        rows = await session.scalars(
            select(ExecutionDelivery)
            .where(ExecutionDelivery.execution_attempt_id == attempt_id)
            .order_by(ExecutionDelivery.delivery_number)
        )
        return list(rows)

    async def create_reply(self, session: AsyncSession, reply: ExecutionReply) -> ExecutionReply:
        session.add(reply)
        await session.flush()
        await session.refresh(reply)
        return reply

    async def has_reply(self, session: AsyncSession, external_id: str) -> bool:
        return (
            await session.scalar(
                select(func.count()).select_from(ExecutionReply).where(ExecutionReply.external_id == external_id)
            )
            or 0
        ) > 0

    async def list_replies(self, session: AsyncSession, attempt_id: UUID) -> list[ExecutionReply]:
        rows = await session.scalars(
            select(ExecutionReply)
            .where(ExecutionReply.execution_attempt_id == attempt_id)
            .order_by(ExecutionReply.replied_at, ExecutionReply.id)
        )
        return list(rows)

    async def acquire_lease(
        self,
        session: AsyncSession,
        run_id: UUID,
        *,
        owner: str,
        token: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> PipelineRun | None:
        result = await session.execute(
            update(PipelineRun)
            .where(
                PipelineRun.id == run_id,
                PipelineRun.state.in_(ACTIVE_RUN_STATES),
                or_(PipelineRun.lease_token.is_(None), PipelineRun.lease_expires_at <= now),
            )
            .values(lease_owner=owner, lease_token=token, lease_expires_at=expires_at)
            .returning(PipelineRun)
        )
        return result.scalar_one_or_none()

    async def renew_lease(
        self,
        session: AsyncSession,
        run_id: UUID,
        *,
        owner: str,
        token: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> PipelineRun | None:
        result = await session.execute(
            update(PipelineRun)
            .where(
                PipelineRun.id == run_id,
                PipelineRun.lease_owner == owner,
                PipelineRun.lease_token == token,
                PipelineRun.lease_expires_at > now,
            )
            .values(lease_expires_at=expires_at)
            .returning(PipelineRun)
            .execution_options(synchronize_session="fetch", populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def release_lease(
        self,
        session: AsyncSession,
        run_id: UUID,
        *,
        owner: str,
        token: UUID,
        now: datetime,
    ) -> PipelineRun | None:
        result = await session.execute(
            update(PipelineRun)
            .where(
                PipelineRun.id == run_id,
                PipelineRun.lease_owner == owner,
                PipelineRun.lease_token == token,
                PipelineRun.lease_expires_at > now,
            )
            .values(lease_owner=None, lease_token=None, lease_expires_at=None, updated_at=now)
            .returning(PipelineRun)
        )
        return result.scalar_one_or_none()
