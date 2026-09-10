from typing import Annotated
from uuid import UUID

from app.features.pipelines.schemas import PipelineObservationConfig
from app.features.projects.models import ProjectConnection
from app.features.projects.repos import PROJECT_OBSERVATION_TASK, ProjectRepository
from app.features.projects.schemas import ProjectObservationPayload, ProjectRead, ProjectUpdate, ProjectWrite
from app.features.projects.templates import TEMPLATE_VERSION
from fastapi import Depends
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession


class ProjectError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


class ProjectService:
    def __init__(self, repo: Annotated[ProjectRepository, Depends()]):
        self.repo = repo

    async def get(self, session: AsyncSession, project_id: UUID, *, lock: bool = False) -> ProjectConnection:
        project = await self.repo.get(session, project_id, lock=lock)
        if project is None:
            raise ProjectError(404, "Project connection not found")
        return project

    async def validate(self, session: AsyncSession, data: ProjectWrite, project_id: UUID | None = None) -> None:
        for connector_id, provider in ((data.github_connector_id, "github"), (data.linear_connector_id, "linear")):
            if connector_id is None:
                continue
            connector = await self.repo.connector(session, connector_id)
            if connector is None or connector.provider != provider or not connector.enabled:
                raise ProjectError(422, f"Select an enabled {provider} connector")
        if any(
            row.id != project_id for row in await self.repo.conflicts(session, data.repository, data.linear_project_id)
        ):
            raise ProjectError(409, "Repository or Linear project is already connected")

    async def create(self, session: AsyncSession, data: ProjectWrite) -> ProjectConnection:
        await self.validate(session, data)
        values = data.model_dump(mode="python")
        values["verification"] = data.verification.model_dump(mode="json")
        return await self.repo.save(
            session,
            ProjectConnection(
                **values,
                template_version=TEMPLATE_VERSION if data.template_id else None,
            ),
        )

    async def update(self, session: AsyncSession, project_id: UUID, data: ProjectUpdate) -> ProjectConnection:
        project = await self.get(session, project_id, lock=True)
        if project.revision != data.expected_revision:
            raise ProjectError(409, "Project changed; reload before saving")
        await self.validate(session, data, project_id)
        for key, value in data.model_dump(exclude={"expected_revision", "verification"}).items():
            setattr(project, key, value)
        project.verification = data.verification.model_dump(mode="json")
        project.template_version = TEMPLATE_VERSION if data.template_id else None
        project.revision += 1
        project.last_check = None
        return await self.repo.save(session, project)

    async def delete(self, session: AsyncSession, project_id: UUID) -> None:
        project = await self.get(session, project_id, lock=True)
        if await self.repo.has_schedules(session, project_id):
            raise ProjectError(409, "Remove the project's observation schedules before deleting it")
        await self.repo.delete(session, project)

    async def import_schedule(self, session: AsyncSession, schedule_id: UUID) -> ProjectConnection:
        schedule = await self.repo.schedule(session, schedule_id)
        if schedule is None:
            raise ProjectError(404, "Schedule not found")
        if schedule.task_func == PROJECT_OBSERVATION_TASK:
            payload = ProjectObservationPayload.model_validate(schedule.payload)
            return await self.get(session, payload.project_id)
        if schedule.task_func != "pipeline.observe":
            raise ProjectError(422, "Only legacy pipeline.observe schedules can be imported")
        try:
            old = PipelineObservationConfig.model_validate(schedule.payload)
        except ValidationError:
            raise ProjectError(422, "Legacy observation payload is invalid; correct it before importing") from None
        data = ProjectWrite(
            name=schedule.name,
            repository=old.repository,
            linear_project_id=old.linear_project_id,
            github_connector_id=old.github_connector_id,
            verification=old.verification,
        )
        matches = await self.repo.conflicts(session, data.repository, data.linear_project_id)
        if matches:
            if len(matches) != 1:
                raise ProjectError(409, "Legacy mapping conflicts with existing project connections")
            project = matches[0]
            existing = ProjectRead.model_validate(project)
            if (
                existing.repository != data.repository
                or existing.linear_project_id != data.linear_project_id
                or existing.github_connector_id != data.github_connector_id
                or existing.verification != data.verification
            ):
                raise ProjectError(409, "Legacy configuration differs from the existing project; nothing was migrated")
            await self.validate(session, data, project.id)
        else:
            project = await self.create(session, data)
        schedule.task_func = PROJECT_OBSERVATION_TASK
        schedule.payload = ProjectObservationPayload(project_id=project.id, pull_numbers=old.pull_numbers).model_dump(
            mode="json"
        )
        await session.flush()
        return project
