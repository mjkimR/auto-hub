import pytest
from app.features.schedule_configs.models import ScheduleConfig
from app.features.schedule_configs.repos import ScheduleConfigRepository
from app.features.schedule_configs.services import ScheduleConfigContextKwargs, ScheduleConfigService
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestGetScheduleConfig:
    async def test_get_schedule_config_success(
        self,
        session: AsyncSession,
        make_db,
    ):
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            name="get_test_schedule",
            task_func="tasks.example_task",
            interval_seconds=60,
        )

        service = resolve_dependency(ScheduleConfigService)
        context: ScheduleConfigContextKwargs = {}

        retrieved = await service.get(session, config.id, context=context)

        assert retrieved is not None
        assert retrieved.id == config.id
        assert retrieved.name == "get_test_schedule"
        assert retrieved.task_func == "tasks.example_task"
        assert retrieved.interval_seconds == 60

    async def test_get_multi_schedule_configs(
        self,
        session: AsyncSession,
        make_db_batch,
    ):
        await make_db_batch(
            ScheduleConfigRepository,
            _size=3,
            task_func="tasks.example_task",
            interval_seconds=60,
        )

        service = resolve_dependency(ScheduleConfigService)
        context: ScheduleConfigContextKwargs = {}

        results = await service.get_multi(session, context=context)

        assert len(results.items) == 3
