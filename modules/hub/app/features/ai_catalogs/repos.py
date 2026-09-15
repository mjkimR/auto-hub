from datetime import datetime
from uuid import UUID

from app.features.ai_catalogs.models import AICatalog
from app.features.project_management.pipeline_runs.models import (
    ExecutionAttempt,
    ExecutionAttemptState,
    PipelineRun,
    PipelineRunState,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class AICatalogRepository:
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

    async def active_run_count(
        self, session: AsyncSession, catalog_id: UUID, exclude_run_id: UUID | None = None
    ) -> int:
        """Count runs holding catalog capacity: a delivered mention or an admitted, possibly uncertain, post.

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
        return int(await session.scalar(select(func.count()).select_from(PipelineRun).where(*filters)) or 0)
