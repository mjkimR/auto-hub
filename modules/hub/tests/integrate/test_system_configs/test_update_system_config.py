import pytest
from app.features.system_configs.models import SystemConfig
from app.features.system_configs.repos import SystemConfigRepository
from app.features.system_configs.schemas import SystemConfigPatch, SystemConfigPut
from app.features.system_configs.services import SystemConfigContextKwargs
from app.features.system_configs.usecases.crud import PatchSystemConfigUseCase, PutSystemConfigUseCase
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestUpdateSystemConfig:
    async def test_put_system_config_success(
        self,
        session: AsyncSession,
        make_db,
    ):
        config: SystemConfig = await make_db(
            SystemConfigRepository,
            name="put_target_config",
            data={"old": "value"},
        )

        use_case = resolve_dependency(PutSystemConfigUseCase)
        context: SystemConfigContextKwargs = {}

        update_data = SystemConfigPut(
            name="put_target_config",
            data={"new": "value", "updated": True},
        )
        updated = await use_case.execute(config.id, update_data, context=context)

        assert updated is not None
        assert updated.id == config.id
        assert updated.data == {"new": "value", "updated": True}

        await session.refresh(config)
        assert config.data == {"new": "value", "updated": True}

    async def test_patch_system_config_data_success(
        self,
        session: AsyncSession,
        make_db,
    ):
        config: SystemConfig = await make_db(
            SystemConfigRepository,
            name="patch_target_config",
            data={"keep": "this", "change": "old"},
        )

        use_case = resolve_dependency(PatchSystemConfigUseCase)
        context: SystemConfigContextKwargs = {}

        patch_data = SystemConfigPatch(data={"change": "new"})
        patched = await use_case.execute(config.id, patch_data, context=context)

        assert patched is not None
        assert patched.id == config.id
        assert patched.data == {"change": "new"}

    async def test_patch_system_config_name_success(
        self,
        session: AsyncSession,
        make_db,
    ):
        config: SystemConfig = await make_db(
            SystemConfigRepository,
            name="old_config_name",
            data={},
        )

        use_case = resolve_dependency(PatchSystemConfigUseCase)
        context: SystemConfigContextKwargs = {}

        patch_data = SystemConfigPatch(name="new_config_name")
        patched = await use_case.execute(config.id, patch_data, context=context)

        assert patched is not None
        assert patched.name == "new_config_name"

        await session.refresh(config)
        assert config.name == "new_config_name"
