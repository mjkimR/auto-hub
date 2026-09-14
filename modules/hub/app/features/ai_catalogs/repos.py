from datetime import datetime
from uuid import UUID

from app.features.ai_catalogs.models import AICatalog
from app.features.project_management.pipeline_runs.models import PipelineRun, PipelineRunState
from sqlalchemy import func, select
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

    async def active_run_count(self, session: AsyncSession, catalog_id: UUID, exclude_run_id: UUID) -> int:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(PipelineRun)
                .where(
                    PipelineRun.ai_catalog_id == catalog_id,
                    PipelineRun.id != exclude_run_id,
                    PipelineRun.state.in_((PipelineRunState.DISPATCHING, PipelineRunState.IMPLEMENTING)),
                )
            )
            or 0
        )
