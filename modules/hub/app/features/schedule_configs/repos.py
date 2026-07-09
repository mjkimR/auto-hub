from app.features.schedule_configs.models import ScheduleConfig
from app.features.schedule_configs.schemas import ScheduleConfigCreate, ScheduleConfigPatch, ScheduleConfigPut
from app_layer_base.base.repos.base import BaseRepository


class ScheduleConfigRepository(
    BaseRepository[ScheduleConfig, ScheduleConfigCreate, ScheduleConfigPut, ScheduleConfigPatch]
):
    model = ScheduleConfig
