from typing import Annotated

from app.features.configuration.system_configs.models import SystemConfig
from app.features.configuration.system_configs.schemas import SystemConfigCreate, SystemConfigPatch, SystemConfigPut
from app.features.configuration.system_configs.services import SystemConfigContextKwargs, SystemConfigService
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends


class GetSystemConfigUseCase(BaseGetUseCase[SystemConfigService, SystemConfig, SystemConfigContextKwargs]):
    def __init__(self, service: Annotated[SystemConfigService, Depends()]) -> None:
        super().__init__(service)


class GetMultiSystemConfigUseCase(BaseGetMultiUseCase[SystemConfigService, SystemConfig, SystemConfigContextKwargs]):
    def __init__(self, service: Annotated[SystemConfigService, Depends()]) -> None:
        super().__init__(service)


class CreateSystemConfigUseCase(
    BaseCreateUseCase[SystemConfigService, SystemConfig, SystemConfigCreate, SystemConfigContextKwargs]
):
    def __init__(self, service: Annotated[SystemConfigService, Depends()]) -> None:
        super().__init__(service)


class PatchSystemConfigUseCase(
    BasePatchUseCase[SystemConfigService, SystemConfig, SystemConfigPut, SystemConfigPatch, SystemConfigContextKwargs]
):
    def __init__(self, service: Annotated[SystemConfigService, Depends()]) -> None:
        super().__init__(service)


class PutSystemConfigUseCase(
    BasePutUseCase[SystemConfigService, SystemConfig, SystemConfigPut, SystemConfigPatch, SystemConfigContextKwargs]
):
    def __init__(self, service: Annotated[SystemConfigService, Depends()]) -> None:
        super().__init__(service)


class DeleteSystemConfigUseCase(BaseDeleteUseCase[SystemConfigService, SystemConfig, SystemConfigContextKwargs]):
    def __init__(self, service: Annotated[SystemConfigService, Depends()]) -> None:
        super().__init__(service)
