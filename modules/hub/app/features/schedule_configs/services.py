from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any

from app.common.utils.calc_schedule import calc_next_run as _calc_next_run_util
from app.features.schedule_configs.models import ScheduleConfig
from app.features.schedule_configs.repos import ScheduleConfigRepository
from app.features.schedule_configs.schemas import ScheduleConfigCreate, ScheduleConfigPatch, ScheduleConfigPut
from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from app_layer_base.base.services.exists_check_hook import ExistsCheckHook
from app_layer_base.base.services.hooks import CreateHook, Operation, UpdateHook
from app_layer_base.base.services.unique_constraints_hook import UniqueConstraintHook
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.sql.expression import ColumnElement


class ScheduleConfigContextKwargs(BaseContextKwargs):
    pass


def _calc_next_run(cron_expression: str | None, interval_seconds: int | None) -> datetime | None:
    """Calculate next_run_at based on given schedule config.

    Returns ``None`` when neither *cron_expression* nor *interval_seconds* is set,
    which signals that the config should be executed immediately on its first dispatch tick.
    Otherwise delegates to :func:`app.common.utils.calc_schedule.calc_next_run`.
    """
    if not cron_expression and not interval_seconds:
        return None
    return _calc_next_run_util(cron_expression, interval_seconds)


class ScheduleConfigUniqueHook(UniqueConstraintHook[ScheduleConfig, ScheduleConfigContextKwargs]):
    async def constraints(
        self,
        op: Operation[ScheduleConfigContextKwargs],
        data: BaseModel,
    ) -> AsyncIterator[tuple[ColumnElement[bool], str]]:
        name = getattr(data, "name", None)
        if name:
            yield ScheduleConfig.name == name, "ScheduleConfig name must be unique."


class ScheduleConfigNextRunHook(
    CreateHook[ScheduleConfig, ScheduleConfigContextKwargs],
    UpdateHook[ScheduleConfig, ScheduleConfigContextKwargs],
):
    """Keeps ``next_run_at`` consistent with the schedule shape (cron/interval).

    Create always computes it; update recomputes it only when the shape changes.
    The dispatcher's own ``next_run_at`` stamping after a run is a separate,
    deliberate path (it advances the schedule from "now", not from the shape).
    """

    _STATE_KEY = "schedule_config_next_run_current_row"

    def create_prepare_fields(
        self,
        op: Operation[ScheduleConfigContextKwargs],
        data: BaseModel,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        cron = getattr(data, "cron_expression", None)
        interval = getattr(data, "interval_seconds", None)
        return {**fields, "next_run_at": _calc_next_run(cron, interval)}

    @asynccontextmanager
    async def update_context(
        self,
        op: Operation[ScheduleConfigContextKwargs],
        pk: PrimaryKeyType,
        data: BaseModel,
        partial: bool = True,
    ) -> AsyncGenerator[None]:
        # ExistsCheckHook has already loaded this row into the session's
        # identity map, so this fetch issues no extra query.
        op.state[self._STATE_KEY] = await op.repo.get_by_pk(op.session, pk)
        yield

    def update_prepare_fields(
        self,
        op: Operation[ScheduleConfigContextKwargs],
        data: BaseModel,
        fields: dict[str, Any],
        partial: bool = True,
    ) -> dict[str, Any]:
        current = op.state.get(self._STATE_KEY)
        if current is None:
            return fields

        if partial:
            patch_data = data.model_dump(exclude_unset=True)
            new_cron = patch_data.get("cron_expression", current.cron_expression)
            new_interval = patch_data.get("interval_seconds", current.interval_seconds)
        else:
            new_cron = getattr(data, "cron_expression", None)
            new_interval = getattr(data, "interval_seconds", None)

        if (new_cron != current.cron_expression) or (new_interval != current.interval_seconds):
            return {**fields, "next_run_at": _calc_next_run(new_cron, new_interval)}
        return fields


class ScheduleConfigService(
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
        # Contexts are entered in this order and exited in reverse.
        self.hooks = (
            ExistsCheckHook(),  # Reject update/delete of a row that does not exist
            ScheduleConfigUniqueHook(),  # Reject duplicate names before create/update
            ScheduleConfigNextRunHook(),  # Keep next_run_at consistent with cron/interval
        )

    @property
    def repo(self) -> ScheduleConfigRepository:
        return self._repo

    @property
    def context_model(self):
        return ScheduleConfigContextKwargs
