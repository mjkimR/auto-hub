from typing import Annotated

from app.features.scheduling.schedule_jobs.models import ScheduleJob
from app.features.scheduling.schedule_jobs.repos import ScheduleJobRepository
from app.features.scheduling.schedule_jobs.schemas import ScheduleJobCreate, ScheduleJobPatch, ScheduleJobPut
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from fastapi import Depends


class ScheduleJobContextKwargs(BaseContextKwargs):
    pass


class ScheduleJobService(
    BaseCreateServiceMixin[ScheduleJobRepository, ScheduleJob, ScheduleJobCreate, ScheduleJobContextKwargs],
    BaseGetMultiServiceMixin[ScheduleJobRepository, ScheduleJob, ScheduleJobContextKwargs],
    BaseGetServiceMixin[ScheduleJobRepository, ScheduleJob, ScheduleJobContextKwargs],
    BaseUpdateServiceMixin[
        ScheduleJobRepository, ScheduleJob, ScheduleJobPut, ScheduleJobPatch, ScheduleJobContextKwargs
    ],
    BaseDeleteServiceMixin[ScheduleJobRepository, ScheduleJob, ScheduleJobContextKwargs],
):
    def __init__(self, repo: Annotated[ScheduleJobRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> ScheduleJobRepository:
        return self._repo

    @property
    def context_model(self):
        return ScheduleJobContextKwargs
