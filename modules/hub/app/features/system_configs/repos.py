from app.features.system_configs.models import SystemConfig
from app.features.system_configs.schemas import SystemConfigCreate, SystemConfigPatch, SystemConfigPut
from app_layer_base.base.repos.base import BaseRepository
from sqlalchemy.ext.asyncio import AsyncSession


class SystemConfigRepository(BaseRepository[SystemConfig, SystemConfigCreate, SystemConfigPut, SystemConfigPatch]):
    model = SystemConfig

    async def get_by_name(self, session: AsyncSession, name: str) -> SystemConfig | None:
        return await self.get(session, where=SystemConfig.name == name)
