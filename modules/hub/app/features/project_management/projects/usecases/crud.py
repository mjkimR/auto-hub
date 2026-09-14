from typing import Annotated
from uuid import UUID

from app.features.project_management.projects.schemas import ProjectList, ProjectRead, ProjectUpdate, ProjectWrite
from app.features.project_management.projects.services import ProjectError, ProjectService
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends
from sqlalchemy.exc import IntegrityError


class ProjectUseCase:
    def __init__(self, service: Annotated[ProjectService, Depends()]):
        self.service = service

    async def list(self, offset: int, limit: int) -> ProjectList:
        async with AsyncTransaction() as session:
            rows, total = await self.service.repo.get_multi(session, offset, limit)
            return ProjectList(items=[ProjectRead.model_validate(row) for row in rows], total_count=total)

    async def get(self, project_id: UUID) -> ProjectRead:
        async with AsyncTransaction() as session:
            return ProjectRead.model_validate(await self.service.get(session, project_id))

    async def create(self, data: ProjectWrite) -> ProjectRead:
        try:
            async with AsyncTransaction() as session:
                return ProjectRead.model_validate(await self.service.create(session, data))
        except IntegrityError:
            raise ProjectError(409, "Project mapping conflicts or a connector was removed; reload and retry") from None

    async def update(self, project_id: UUID, data: ProjectUpdate) -> ProjectRead:
        try:
            async with AsyncTransaction() as session:
                return ProjectRead.model_validate(await self.service.update(session, project_id, data))
        except IntegrityError:
            raise ProjectError(409, "Project mapping conflicts or a connector was removed; reload and retry") from None

    async def delete(self, project_id: UUID) -> None:
        async with AsyncTransaction() as session:
            await self.service.delete(session, project_id)

    async def import_schedule(self, schedule_id: UUID) -> ProjectRead:
        try:
            async with AsyncTransaction() as session:
                return ProjectRead.model_validate(await self.service.import_schedule(session, schedule_id))
        except IntegrityError:
            raise ProjectError(409, "Project mapping changed during import; nothing was migrated") from None
