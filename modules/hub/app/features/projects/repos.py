from uuid import UUID

from app.features.connectors.models import Connector
from app.features.pipeline_runs.models import PipelineRun
from app.features.projects.models import Project
from app.features.schedule_configs.models import ScheduleConfig
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_OBSERVATION_TASK = "pipeline.observe_project"
PROJECT_DISPATCH_TASK = "pipeline.dispatch_project"


class ProjectRepository:
    async def get(self, session: AsyncSession, project_id: UUID, *, lock: bool = False) -> Project | None:
        stmt = select(Project).where(Project.id == project_id)
        if lock:
            stmt = stmt.with_for_update()
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_multi(self, session: AsyncSession, offset: int, limit: int) -> tuple[list[Project], int]:
        total = await session.scalar(select(func.count()).select_from(Project))
        rows = await session.scalars(select(Project).order_by(Project.name, Project.id).offset(offset).limit(limit))
        return list(rows), total or 0

    async def conflicts(
        self, session: AsyncSession, repository: str | None, linear_project_id: UUID | None
    ) -> list[Project]:
        clauses = []
        if repository is not None:
            clauses.append(Project.github_repository == repository)
        if linear_project_id is not None:
            clauses.append(Project.linear_project_id == linear_project_id)
        if not clauses:
            return []
        rows = await session.scalars(select(Project).where(or_(*clauses)))
        return list(rows)

    async def connector(self, session: AsyncSession, connector_id: UUID) -> Connector | None:
        return await session.get(Connector, connector_id)

    async def save(self, session: AsyncSession, project: Project) -> Project:
        session.add(project)
        await session.flush()
        await session.refresh(project)
        return project

    async def delete(self, session: AsyncSession, project: Project) -> None:
        await session.delete(project)
        await session.flush()

    async def has_schedules(self, session: AsyncSession, project_id: UUID) -> bool:
        return (
            await session.scalar(
                select(ScheduleConfig.id)
                .where(
                    ScheduleConfig.task_func == PROJECT_OBSERVATION_TASK,
                    ScheduleConfig.payload["project_id"].as_string() == str(project_id),
                )
                .limit(1)
            )
        ) is not None

    async def has_pipeline_runs(self, session: AsyncSession, project_id: UUID) -> bool:
        return (
            await session.scalar(select(PipelineRun.id).where(PipelineRun.project_id == project_id).limit(1))
        ) is not None

    async def schedule(self, session: AsyncSession, schedule_id: UUID) -> ScheduleConfig | None:
        return (
            await session.scalars(select(ScheduleConfig).where(ScheduleConfig.id == schedule_id).with_for_update())
        ).one_or_none()

    async def save_check(self, session: AsyncSession, project_id: UUID, revision: int, report: dict) -> bool:
        result = await session.execute(
            update(Project)
            .where(
                Project.id == project_id,
                Project.revision == revision,
            )
            .values(last_check=report)
        )
        return result.rowcount == 1  # type: ignore[attr-defined]
