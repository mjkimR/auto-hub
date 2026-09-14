from datetime import datetime

import pytest
from app.features.scheduling.schedule_configs.models import ScheduleConfig
from app.features.scheduling.schedule_configs.repos import ScheduleConfigRepository
from app.features.scheduling.schedule_configs.schemas import ScheduleConfigPatch, ScheduleConfigPut
from app.features.scheduling.schedule_configs.services import ScheduleConfigContextKwargs
from app.features.scheduling.schedule_configs.usecases.crud import PatchScheduleConfigUseCase, PutScheduleConfigUseCase
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestUpdateScheduleConfig:
    async def test_put_schedule_config_success(
        self,
        session: AsyncSession,
        make_db,
    ):
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            name="put_target_schedule",
            task_func="tasks.old_task",
            interval_seconds=60,
        )

        use_case = resolve_dependency(PutScheduleConfigUseCase)
        context: ScheduleConfigContextKwargs = {}

        update_data = ScheduleConfigPut(
            name="put_target_schedule",
            task_func="tasks.new_task",
            interval_seconds=120,
            payload={"updated": True},
        )
        updated = await use_case.execute(config.id, update_data, context=context)

        assert updated is not None
        assert updated.id == config.id
        assert updated.task_func == "tasks.new_task"
        assert updated.interval_seconds == 120
        assert updated.payload == {"updated": True}
        assert updated.next_run_at is not None
        assert isinstance(updated.next_run_at, datetime)

        await session.refresh(config)
        assert config.task_func == "tasks.new_task"
        assert config.interval_seconds == 120
        assert config.next_run_at is not None

    async def test_patch_schedule_config_enabled_flag(
        self,
        session: AsyncSession,
        make_db,
    ):
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            name="patch_enable_schedule",
            task_func="tasks.example_task",
            interval_seconds=60,
            enabled=True,
        )

        use_case = resolve_dependency(PatchScheduleConfigUseCase)
        context: ScheduleConfigContextKwargs = {}

        patch_data = ScheduleConfigPatch(enabled=False)
        patched = await use_case.execute(config.id, patch_data, context=context)

        assert patched is not None
        assert patched.id == config.id
        assert patched.enabled is False

        await session.refresh(config)
        assert config.enabled is False

    async def test_patch_schedule_config_task_func(
        self,
        session: AsyncSession,
        make_db,
    ):
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            name="patch_task_func_schedule",
            task_func="tasks.old_func",
            interval_seconds=30,
        )

        use_case = resolve_dependency(PatchScheduleConfigUseCase)
        context: ScheduleConfigContextKwargs = {}

        patch_data = ScheduleConfigPatch(task_func="tasks.new_func")
        patched = await use_case.execute(config.id, patch_data, context=context)

        assert patched is not None
        assert patched.task_func == "tasks.new_func"

        await session.refresh(config)
        assert config.task_func == "tasks.new_func"

    async def test_patch_schedule_config_interval_change_recalculates_next_run_at(
        self,
        session: AsyncSession,
        make_db,
    ):
        """next_run_at should be recalculated when interval_seconds is changed."""
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            name="patch_interval_schedule",
            task_func="tasks.example_task",
            interval_seconds=60,
        )
        original_next_run_at = config.next_run_at

        use_case = resolve_dependency(PatchScheduleConfigUseCase)
        context: ScheduleConfigContextKwargs = {}

        patch_data = ScheduleConfigPatch(interval_seconds=300)
        patched = await use_case.execute(config.id, patch_data, context=context)

        assert patched is not None
        assert patched.interval_seconds == 300
        assert patched.next_run_at is not None
        assert isinstance(patched.next_run_at, datetime)
        assert patched.next_run_at != original_next_run_at

    async def test_patch_schedule_config_clear_schedule_sets_next_run_at_none(
        self,
        session: AsyncSession,
        make_db,
    ):
        """Removing interval_seconds should set next_run_at=None, triggering immediately."""
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            name="patch_clear_schedule",
            task_func="tasks.example_task",
            interval_seconds=60,
        )

        use_case = resolve_dependency(PatchScheduleConfigUseCase)
        context: ScheduleConfigContextKwargs = {}

        patch_data = ScheduleConfigPatch(interval_seconds=None)
        patched = await use_case.execute(config.id, patch_data, context=context)

        assert patched is not None
        assert patched.interval_seconds is None
        assert patched.cron_expression is None
        assert patched.next_run_at is None

        await session.refresh(config)
        assert config.next_run_at is None
