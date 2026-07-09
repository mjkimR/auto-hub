from typing import Annotated

from app.features.schedule_configs.models import ScheduleConfig
from app.features.schedule_configs.schemas import ScheduleConfigCreate, ScheduleConfigPatch, ScheduleConfigPut
from app.features.schedule_configs.services import ScheduleConfigContextKwargs, ScheduleConfigService
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends


class GetScheduleConfigUseCase(BaseGetUseCase[ScheduleConfigService, ScheduleConfig, ScheduleConfigContextKwargs]):
    def __init__(self, service: Annotated[ScheduleConfigService, Depends()]) -> None:
        super().__init__(service)


class GetMultiScheduleConfigUseCase(
    BaseGetMultiUseCase[ScheduleConfigService, ScheduleConfig, ScheduleConfigContextKwargs]
):
    def __init__(self, service: Annotated[ScheduleConfigService, Depends()]) -> None:
        super().__init__(service)


class CreateScheduleConfigUseCase(
    BaseCreateUseCase[ScheduleConfigService, ScheduleConfig, ScheduleConfigCreate, ScheduleConfigContextKwargs]
):
    def __init__(self, service: Annotated[ScheduleConfigService, Depends()]) -> None:
        super().__init__(service)


class PatchScheduleConfigUseCase(
    BasePatchUseCase[
        ScheduleConfigService, ScheduleConfig, ScheduleConfigPut, ScheduleConfigPatch, ScheduleConfigContextKwargs
    ]
):
    def __init__(self, service: Annotated[ScheduleConfigService, Depends()]) -> None:
        super().__init__(service)


class PutScheduleConfigUseCase(
    BasePutUseCase[
        ScheduleConfigService, ScheduleConfig, ScheduleConfigPut, ScheduleConfigPatch, ScheduleConfigContextKwargs
    ]
):
    def __init__(self, service: Annotated[ScheduleConfigService, Depends()]) -> None:
        super().__init__(service)


class DeleteScheduleConfigUseCase(
    BaseDeleteUseCase[ScheduleConfigService, ScheduleConfig, ScheduleConfigContextKwargs]
):
    def __init__(self, service: Annotated[ScheduleConfigService, Depends()]) -> None:
        super().__init__(service)
