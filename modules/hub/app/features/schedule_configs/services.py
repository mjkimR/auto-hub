import uuid
from datetime import datetime
from typing import Annotated, Any

from app.common.utils.calc_schedule import calc_next_run as _calc_next_run_util
from app.features.schedule_configs.models import ScheduleConfig
from app.features.schedule_configs.repos import ScheduleConfigRepository
from app.features.schedule_configs.schemas import ScheduleConfigCreate, ScheduleConfigPatch, ScheduleConfigPut
from app_layer_base.base.exceptions.basic import NotFoundException
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


class ScheduleConfigContextKwargs(BaseContextKwargs):
    pass


class ScheduleConfigService(
    UniqueConstraintHooksMixin[ScheduleConfig, ScheduleConfigContextKwargs],
    ExistsCheckHooksMixin[ScheduleConfig, ScheduleConfigContextKwargs],
    BaseCreateServiceMixin[ScheduleConfigRepository, ScheduleConfig, ScheduleConfigCreate, ScheduleConfigContextKwargs],
    BaseGetMultiServiceMixin[ScheduleConfigRepository, ScheduleConfig, ScheduleConfigContextKwargs],
    BaseGetServiceMixin[ScheduleConfigRepository, ScheduleConfig, ScheduleConfigContextKwargs],
    BaseUpdateServiceMixin[
        ScheduleConfigRepository, ScheduleConfig, ScheduleConfigPut, ScheduleConfigPatch, ScheduleConfigContextKwargs
    ],
    BaseDeleteServiceMixin[ScheduleConfigRepository, ScheduleConfig, ScheduleConfigContextKwargs],
):
    def __init__(self, repo: Annotated[ScheduleConfigRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> ScheduleConfigRepository:
        return self._repo

    @property
    def context_model(self):
        return ScheduleConfigContextKwargs

    async def _unique_constraints(
        self,
        obj_data: ScheduleConfigCreate | ScheduleConfigPut | ScheduleConfigPatch,
        context: ScheduleConfigContextKwargs,
    ):
        if obj_data.name:
            yield self.repo.model.name == obj_data.name, "ScheduleConfig name must be unique."

    def _calc_next_run(self, cron_expression: str | None, interval_seconds: int | None) -> datetime | None:
        """Calculate next_run_at based on given schedule config.

        Returns ``None`` when neither *cron_expression* nor *interval_seconds* is set,
        which signals that the config should be executed immediately on its first dispatch tick.
        Otherwise delegates to :func:`app.common.utils.calc_schedule.calc_next_run`.
        """
        if not cron_expression and not interval_seconds:
            return None
        return _calc_next_run_util(cron_expression, interval_seconds)

    async def create(
        self,
        session: AsyncSession,
        obj_data: ScheduleConfigCreate,
        context: ScheduleConfigContextKwargs | None = None,
        **update_fields: Any,
    ) -> ScheduleConfig:
        update_fields["next_run_at"] = self._calc_next_run(obj_data.cron_expression, obj_data.interval_seconds)
        return await super().create(session, obj_data, context, **update_fields)

    async def put(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        obj_data: ScheduleConfigPut,
        context: ScheduleConfigContextKwargs | None = None,
        **update_fields: Any,
    ) -> ScheduleConfig | None:
        exists = await self.repo.get_by_pk(session, obj_id)
        if not exists:
            raise NotFoundException(f"ScheduleConfig with id {obj_id} does not exist.")

        if (obj_data.cron_expression != exists.cron_expression) or (
            obj_data.interval_seconds != exists.interval_seconds
        ):
            update_fields["next_run_at"] = self._calc_next_run(obj_data.cron_expression, obj_data.interval_seconds)

        return await super().put(session, obj_id, obj_data, context, **update_fields)

    async def patch(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        obj_data: ScheduleConfigPatch,
        context: ScheduleConfigContextKwargs | None = None,
        **update_fields: Any,
    ) -> ScheduleConfig | None:
        exists = await self.repo.get_by_pk(session, obj_id)
        if not exists:
            raise NotFoundException(f"ScheduleConfig with id {obj_id} does not exist.")

        patch_data = obj_data.model_dump(exclude_unset=True)

        new_cron = patch_data.get("cron_expression", exists.cron_expression)
        new_interval = patch_data.get("interval_seconds", exists.interval_seconds)

        if (new_cron != exists.cron_expression) or (new_interval != exists.interval_seconds):
            update_fields["next_run_at"] = self._calc_next_run(new_cron, new_interval)

        return await super().patch(session, obj_id, obj_data, context, **update_fields)
