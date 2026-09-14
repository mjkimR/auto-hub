import uuid

import pytest
from app.features.configuration.system_configs.models import SystemConfig
from app.features.configuration.system_configs.repos import SystemConfigRepository
from app.features.configuration.system_configs.services import SystemConfigContextKwargs
from app.features.configuration.system_configs.usecases.crud import DeleteSystemConfigUseCase
from app_layer_base.base.exceptions.basic import NotFoundException
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestDeleteSystemConfig:
    async def test_delete_system_config_success(
        self,
        session: AsyncSession,
        make_db,
    ):
        config: SystemConfig = await make_db(
            SystemConfigRepository,
            name="delete_target_config",
            data={"to": "be_deleted"},
        )

        use_case = resolve_dependency(DeleteSystemConfigUseCase)
        context: SystemConfigContextKwargs = {}

        await use_case.execute(config.id, context=context)

        config_id = config.id
        session.expire_all()
        db_config = await session.get(SystemConfig, config_id)
        assert db_config is None

    async def test_delete_system_config_not_found(
        self,
        session: AsyncSession,
    ):
        use_case = resolve_dependency(DeleteSystemConfigUseCase)
        context: SystemConfigContextKwargs = {}

        with pytest.raises(NotFoundException):
            await use_case.execute(uuid.uuid4(), context=context)
