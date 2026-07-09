from app.features.system_configs.models import SystemConfig
from app.features.system_configs.schemas import SystemConfigCreate, SystemConfigPatch, SystemConfigPut
from app_layer_base.base.repos.base import BaseRepository


class SystemConfigRepository(BaseRepository[SystemConfig, SystemConfigCreate, SystemConfigPut, SystemConfigPatch]):
    model = SystemConfig
