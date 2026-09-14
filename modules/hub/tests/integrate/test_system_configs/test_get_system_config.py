import pytest
from app.features.configuration.system_configs.models import SystemConfig
from app.features.configuration.system_configs.repos import SystemConfigRepository
from app.features.configuration.system_configs.services import SystemConfigContextKwargs, SystemConfigService
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestGetSystemConfig:
    async def test_get_system_config_success(
        self,
        session: AsyncSession,
        make_db,
    ):
        config: SystemConfig = await make_db(
            SystemConfigRepository,
            name="get_test_config",
            data={"foo": "bar"},
        )

        service = resolve_dependency(SystemConfigService)
        context: SystemConfigContextKwargs = {}

        retrieved = await service.get(session, config.id, context=context)

        assert retrieved is not None
        assert retrieved.id == config.id
        assert retrieved.name == "get_test_config"
        assert retrieved.data == {"foo": "bar"}

    async def test_get_multi_system_configs(
        self,
        session: AsyncSession,
        make_db_batch,
    ):
        await make_db_batch(SystemConfigRepository, _size=3, data={})

        service = resolve_dependency(SystemConfigService)
        context: SystemConfigContextKwargs = {}

        results = await service.get_multi(session, context=context)

        assert len(results.items) == 3
