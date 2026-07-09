from typing import Annotated

from app.features.schedule_jobs.models import ScheduleJob
from app.features.schedule_jobs.schemas import ScheduleJobCreate, ScheduleJobPatch, ScheduleJobPut
from app.features.schedule_jobs.services import ScheduleJobContextKwargs, ScheduleJobService
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends


class GetScheduleJobUseCase(BaseGetUseCase[ScheduleJobService, ScheduleJob, ScheduleJobContextKwargs]):
    def __init__(self, service: Annotated[ScheduleJobService, Depends()]) -> None:
        super().__init__(service)


class GetMultiScheduleJobUseCase(BaseGetMultiUseCase[ScheduleJobService, ScheduleJob, ScheduleJobContextKwargs]):
    def __init__(self, service: Annotated[ScheduleJobService, Depends()]) -> None:
        super().__init__(service)


class CreateScheduleJobUseCase(
    BaseCreateUseCase[ScheduleJobService, ScheduleJob, ScheduleJobCreate, ScheduleJobContextKwargs]
):
    def __init__(self, service: Annotated[ScheduleJobService, Depends()]) -> None:
        super().__init__(service)


class PatchScheduleJobUseCase(
    BasePatchUseCase[ScheduleJobService, ScheduleJob, ScheduleJobPut, ScheduleJobPatch, ScheduleJobContextKwargs]
):
    def __init__(self, service: Annotated[ScheduleJobService, Depends()]) -> None:
        super().__init__(service)


class PutScheduleJobUseCase(
    BasePutUseCase[ScheduleJobService, ScheduleJob, ScheduleJobPut, ScheduleJobPatch, ScheduleJobContextKwargs]
):
    def __init__(self, service: Annotated[ScheduleJobService, Depends()]) -> None:
        super().__init__(service)


class DeleteScheduleJobUseCase(BaseDeleteUseCase[ScheduleJobService, ScheduleJob, ScheduleJobContextKwargs]):
    def __init__(self, service: Annotated[ScheduleJobService, Depends()]) -> None:
        super().__init__(service)
