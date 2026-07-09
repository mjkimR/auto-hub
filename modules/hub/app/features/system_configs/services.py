from typing import Annotated

from app.features.system_configs.models import SystemConfig
from app.features.system_configs.repos import SystemConfigRepository
from app.features.system_configs.schemas import SystemConfigCreate, SystemConfigPatch, SystemConfigPut
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from app_layer_base.base.services.exists_check_hook import ExistsCheckHooksMixin
from app_layer_base.base.services.unique_constraints_hook import UniqueConstraintHooksMixin
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


class SystemConfigContextKwargs(BaseContextKwargs):
    pass


class SystemConfigService(
    UniqueConstraintHooksMixin[
        SystemConfig, SystemConfigContextKwargs
    ],  # Ensure unique constraints before create/update
    ExistsCheckHooksMixin[SystemConfig, SystemConfigContextKwargs],  # Ensure existence checks before operations
    BaseCreateServiceMixin[SystemConfigRepository, SystemConfig, SystemConfigCreate, SystemConfigContextKwargs],
    BaseGetMultiServiceMixin[SystemConfigRepository, SystemConfig, SystemConfigContextKwargs],
    BaseGetServiceMixin[SystemConfigRepository, SystemConfig, SystemConfigContextKwargs],
    BaseUpdateServiceMixin[
        SystemConfigRepository, SystemConfig, SystemConfigPut, SystemConfigPatch, SystemConfigContextKwargs
    ],
    BaseDeleteServiceMixin[SystemConfigRepository, SystemConfig, SystemConfigContextKwargs],
):
    def __init__(self, repo: Annotated[SystemConfigRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> SystemConfigRepository:
        return self._repo

    @property
    def context_model(self):
        return SystemConfigContextKwargs

    async def _unique_constraints(
        self,
        obj_data: SystemConfigCreate | SystemConfigPut | SystemConfigPatch,
        context: SystemConfigContextKwargs,
    ):
        if obj_data.name:
            yield self.repo.model.name == obj_data.name, "SystemConfig name must be unique."

    async def get_by_name(
        self,
        session: AsyncSession,
        name: str,
        context: SystemConfigContextKwargs | None = None,
    ) -> SystemConfig | None:
        """Get a SystemConfig by its name."""
        return await self.repo.get(session, where=self.repo.model.name == name)
