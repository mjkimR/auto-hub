from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.features.pipeline_runs.models import ACTIVE_RUN_STATES, ExecutionAttempt, ExecutionAttemptState, PipelineRun
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession


class PipelineRunRepository:
    async def get(self, session: AsyncSession, run_id: UUID) -> PipelineRun | None:
        return await session.get(PipelineRun, run_id)

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

    async def get_active(self, session: AsyncSession, project_id: UUID, *, lock: bool = False) -> PipelineRun | None:
        stmt = select(PipelineRun).where(
            PipelineRun.project_id == project_id,
            PipelineRun.state.in_(ACTIVE_RUN_STATES),
        )
        if lock:
            stmt = stmt.with_for_update()
        return (await session.execute(stmt)).scalar_one_or_none()

    async def issue_ids(self, session: AsyncSession, project_id: UUID) -> set[UUID]:
        rows = await session.scalars(select(PipelineRun.linear_issue_id).where(PipelineRun.project_id == project_id))
        return set(rows)

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
            .values(lease_owner=None, lease_token=None, lease_expires_at=None)
            .returning(PipelineRun)
        )
        return result.scalar_one_or_none()
