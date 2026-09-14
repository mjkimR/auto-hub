from datetime import datetime

import pytest
from app.features.scheduling.schedule_configs.models import ScheduleConfig
from app.features.scheduling.schedule_configs.schemas import ScheduleConfigCreate
from app.features.scheduling.schedule_configs.services import ScheduleConfigContextKwargs
from app.features.scheduling.schedule_configs.usecases.crud import CreateScheduleConfigUseCase
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestCreateScheduleConfig:
    async def test_create_schedule_config_with_interval_success(
        self,
        session: AsyncSession,
    ):
        use_case = resolve_dependency(CreateScheduleConfigUseCase)

        config_in = ScheduleConfigCreate(
            name="interval_schedule",
            task_func="tasks.example_task",
            interval_seconds=60,
            payload={"key": "value"},
        )

        context: ScheduleConfigContextKwargs = {}
        created = await use_case.execute(config_in, context=context)

        assert created.name == "interval_schedule"
        assert created.task_func == "tasks.example_task"
        assert created.interval_seconds == 60
        assert created.cron_expression is None
        assert created.payload == {"key": "value"}
        assert created.enabled is True
        assert created.next_run_at is not None
        assert isinstance(created.next_run_at, datetime)

        db_config = await session.get(ScheduleConfig, created.id)
        assert db_config is not None
        assert db_config.name == "interval_schedule"
        assert db_config.next_run_at is not None

    async def test_create_schedule_config_with_cron_success(
        self,
        session: AsyncSession,
    ):
        use_case = resolve_dependency(CreateScheduleConfigUseCase)

        config_in = ScheduleConfigCreate(
            name="cron_schedule",
            task_func="tasks.daily_report",
            cron_expression="0 9 * * 1-5",
        )

        context: ScheduleConfigContextKwargs = {}
        created = await use_case.execute(config_in, context=context)

        assert created.name == "cron_schedule"
        assert created.cron_expression == "0 9 * * 1-5"
        assert created.interval_seconds is None
        assert created.next_run_at is not None
        assert isinstance(created.next_run_at, datetime)

        db_config = await session.get(ScheduleConfig, created.id)
        assert db_config is not None
        assert db_config.next_run_at is not None

    async def test_create_schedule_config_disabled(
        self,
        session: AsyncSession,
    ):
        use_case = resolve_dependency(CreateScheduleConfigUseCase)

        config_in = ScheduleConfigCreate(
            name="disabled_schedule",
            task_func="tasks.example_task",
            interval_seconds=300,
            enabled=False,
        )

        context: ScheduleConfigContextKwargs = {}
        created = await use_case.execute(config_in, context=context)

        assert created.enabled is False
        assert created.next_run_at is not None

        db_config = await session.get(ScheduleConfig, created.id)
        assert db_config is not None
        assert db_config.enabled is False
        assert db_config.next_run_at is not None
