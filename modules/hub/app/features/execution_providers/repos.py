from datetime import datetime
from uuid import UUID

from app.features.execution_providers.models import ExecutionProvider
from app.features.project_management.pipeline_runs.models import PipelineRun, PipelineRunState
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class ExecutionProviderRepository:
    async def list(self, session: AsyncSession) -> list[ExecutionProvider]:
        return list((await session.scalars(select(ExecutionProvider).order_by(ExecutionProvider.key))).all())

    async def get(self, session: AsyncSession, provider_id: UUID, *, lock: bool = False) -> ExecutionProvider | None:
        return await session.get(ExecutionProvider, provider_id, with_for_update=lock)

    async def get_by_key(self, session: AsyncSession, key: str, *, lock: bool = False) -> ExecutionProvider | None:
        return (
            await session.scalars(
                select(ExecutionProvider).where(ExecutionProvider.key == key).with_for_update()
                if lock
                else select(ExecutionProvider).where(ExecutionProvider.key == key)
            )
        ).one_or_none()

    async def held_run_count(self, session: AsyncSession, provider_id: UUID, now: datetime) -> int:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(PipelineRun)
                .where(
                    PipelineRun.execution_provider_id == provider_id,
                    PipelineRun.state.in_(
                        (PipelineRunState.QUEUED, PipelineRunState.DISPATCHING, PipelineRunState.IMPLEMENTING)
                    ),
                )
            )
            or 0
        )

    async def active_run_count(self, session: AsyncSession, provider_id: UUID, exclude_run_id: UUID) -> int:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(PipelineRun)
                .where(
                    PipelineRun.execution_provider_id == provider_id,
                    PipelineRun.id != exclude_run_id,
                    PipelineRun.state.in_((PipelineRunState.DISPATCHING, PipelineRunState.IMPLEMENTING)),
                )
            )
            or 0
        )
