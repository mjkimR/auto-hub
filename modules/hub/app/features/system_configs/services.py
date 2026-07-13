from collections.abc import AsyncIterator
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
from app_layer_base.base.services.exists_check_hook import ExistsCheckHook
from app_layer_base.base.services.hooks import Operation
from app_layer_base.base.services.unique_constraints_hook import UniqueConstraintHook
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import ColumnElement


class SystemConfigContextKwargs(BaseContextKwargs):
    pass


class SystemConfigUniqueHook(UniqueConstraintHook[SystemConfig, SystemConfigContextKwargs]):
    async def constraints(
        self,
        op: Operation[SystemConfigContextKwargs],
        data: BaseModel,
    ) -> AsyncIterator[tuple[ColumnElement[bool], str]]:
        name = getattr(data, "name", None)
        if name:
            yield SystemConfig.name == name, "SystemConfig name must be unique."


class SystemConfigService(
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
        # Contexts are entered in this order and exited in reverse.
        self.hooks = (
            SystemConfigUniqueHook(),  # Reject duplicate names before create/update
            ExistsCheckHook(),  # Reject update/delete of a row that does not exist
        )

    @property
    def repo(self) -> SystemConfigRepository:
        return self._repo

    @property
    def context_model(self):
        return SystemConfigContextKwargs

    async def get_by_name(
        self,
        session: AsyncSession,
        name: str,
        context: SystemConfigContextKwargs | None = None,
    ) -> SystemConfig | None:
        """Get a SystemConfig by its name."""
        return await self.repo.get_by_name(session, name)
