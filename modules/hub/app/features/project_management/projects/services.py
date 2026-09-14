from typing import Annotated
from uuid import UUID

from app.features.project_management.pipelines.schemas import PipelineObservationConfig
from app.features.project_management.projects.models import Project
from app.features.project_management.projects.repos import PROJECT_OBSERVATION_TASK, ProjectRepository
from app.features.project_management.projects.schemas import (
    ProjectObservationPayload,
    ProjectRead,
    ProjectUpdate,
    ProjectWrite,
)
from app.features.project_management.projects.templates import TEMPLATE_VERSION
from app_layer_base.base.exceptions.base import Actor, CustomException, Retry
from fastapi import Depends
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession


class ProjectError(CustomException):
    def __init__(
        self,
        status: int,
        detail: str,
        *,
        actor: Actor | None = None,
        retry: Retry | None = None,
        code: str = "PROJECT_ERROR",
        fix: str | None = None,
    ):
        self.status = status
        self.detail = detail
        super().__init__(
            message=detail,
            status_code=status,
            title="Project Error",
            code=code,
            actor=actor or (Actor.USER if status < 500 else Actor.DEVELOPER),
            retry=retry or (Retry.UNSAFE if status in (404, 422) else Retry.SAFE),
            fix=fix,
        )


class ProjectService:
    def __init__(self, repo: Annotated[ProjectRepository, Depends()]):
        self.repo = repo

    async def get(self, session: AsyncSession, project_id: UUID, *, lock: bool = False) -> Project:
        project = await self.repo.get(session, project_id, lock=lock)
        if project is None:
            raise ProjectError(404, "Project not found")
        return project

    async def validate(self, session: AsyncSession, data: ProjectWrite, project_id: UUID | None = None) -> None:
        if data.github is not None:
            connector = await self.repo.connector(session, data.github.github_connector_id)
            if connector is None or connector.provider != "github" or not connector.enabled:
                raise ProjectError(422, "Select an enabled github connector")
            repository = data.github.repository
            if any(row.id != project_id for row in await self.repo.conflicts(session, repository)):
                raise ProjectError(409, "Repository is already connected")

    async def create(self, session: AsyncSession, data: ProjectWrite) -> Project:
        await self.validate(session, data)
        values = {
            "name": data.name,
            "enabled": data.enabled,
            "github_repository": data.github.repository if data.github else None,
            "github_connector_id": data.github.github_connector_id if data.github else None,
            "verification": data.github.verification.model_dump(mode="json") if data.github else None,
            "template_id": data.github.template_id if data.github else None,
        }
        return await self.repo.save(
            session,
            Project(
                **values,
                template_version=TEMPLATE_VERSION if data.github and data.github.template_id else None,
            ),
        )

    async def update(self, session: AsyncSession, project_id: UUID, data: ProjectUpdate) -> Project:
        project = await self.get(session, project_id, lock=True)
        if project.revision != data.expected_revision:
            raise ProjectError(409, "Project changed; reload before saving")
        await self.validate(session, data, project_id)
        project.name = data.name
        project.enabled = data.enabled
        project.github_repository = data.github.repository if data.github else None
        project.github_connector_id = data.github.github_connector_id if data.github else None
        project.verification = data.github.verification.model_dump(mode="json") if data.github else None
        project.template_id = data.github.template_id if data.github else None
        project.template_version = TEMPLATE_VERSION if data.github and data.github.template_id else None
        project.revision += 1
        project.last_check = None
        return await self.repo.save(session, project)

    async def delete(self, session: AsyncSession, project_id: UUID) -> None:
        project = await self.get(session, project_id, lock=True)
        if await self.repo.has_schedules(session, project_id):
            raise ProjectError(409, "Remove the project's observation schedules before deleting it")
        if await self.repo.has_pipeline_runs(session, project_id):
            raise ProjectError(409, "Pipeline run history prevents deleting this project")
        await self.repo.delete(session, project)

    async def import_schedule(self, session: AsyncSession, schedule_id: UUID) -> Project:
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
        data = ProjectWrite.model_validate(
            {
                "name": schedule.name,
                "github": {
                    "repository": old.repository,
                    "github_connector_id": old.github_connector_id,
                    "verification": old.verification,
                },
            }
        )
        assert data.github is not None
        matches = await self.repo.conflicts(session, data.github.repository)
        if matches:
            if len(matches) != 1:
                raise ProjectError(409, "Legacy mapping conflicts with existing project connections")
            project = matches[0]
            existing = ProjectRead.model_validate(project)
            if existing.github != data.github:
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
