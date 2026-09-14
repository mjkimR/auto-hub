from typing import Annotated
from uuid import UUID

from app.features.project_management.pipelines.schemas import PipelineObservation, PipelineObservationConfig
from app.features.project_management.pipelines.services import (
    PipelineObservationQueryService,
    PipelineObservationService,
)
from fastapi import Depends


class InspectPipelineUseCase:
    def __init__(self, service: Annotated[PipelineObservationService, Depends()]):
        self.service = service

    async def execute(self, config: PipelineObservationConfig) -> PipelineObservation:
        return await self.service.observe(config)


class GetPipelineObservationUseCase:
    def __init__(self, service: Annotated[PipelineObservationQueryService, Depends()]):
        self.service = service

    async def execute(self, schedule_id: UUID) -> PipelineObservation | None:
        return await self.service.get(schedule_id)
