import pytest
from app.features.system_configs.models import SystemConfig
from app.features.system_configs.schemas import SystemConfigCreate
from app.features.system_configs.services import SystemConfigContextKwargs
from app.features.system_configs.usecases.crud import CreateSystemConfigUseCase
from app_layer_base.base.exceptions.basic import ConflictException
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestCreateSystemConfig:
    async def test_create_system_config_success(
        self,
        session: AsyncSession,
    ):
        use_case = resolve_dependency(CreateSystemConfigUseCase)

        config_in = SystemConfigCreate(
            name="test_config_key",
            data={"setting": "value", "enabled": True},
        )

        context: SystemConfigContextKwargs = {}
        created = await use_case.execute(config_in, context=context)

        assert created.name == "test_config_key"
        assert created.data == {"setting": "value", "enabled": True}

        db_config = await session.get(SystemConfig, created.id)
        assert db_config is not None
        assert db_config.name == "test_config_key"

    async def test_create_system_config_empty_data(
        self,
        session: AsyncSession,
    ):
        use_case = resolve_dependency(CreateSystemConfigUseCase)

        config_in = SystemConfigCreate(
            name="empty_data_config",
            data={},
        )

        context: SystemConfigContextKwargs = {}
        created = await use_case.execute(config_in, context=context)

        assert created.name == "empty_data_config"
        assert created.data == {}

        db_config = await session.get(SystemConfig, created.id)
        assert db_config is not None

    async def test_create_system_config_duplicate_name_raises_conflict(
        self,
        make_db,
    ):
        from app.features.system_configs.repos import SystemConfigRepository

        await make_db(SystemConfigRepository, name="duplicate_key", data={})

        use_case = resolve_dependency(CreateSystemConfigUseCase)
        config_in = SystemConfigCreate(name="duplicate_key", data={"new": "data"})
        context: SystemConfigContextKwargs = {}

        with pytest.raises(ConflictException):
            await use_case.execute(config_in, context=context)
