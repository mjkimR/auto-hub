from app.features.schedule_configs.schemas import ScheduleConfigCreate
from polyfactory.factories.pydantic_factory import ModelFactory


class ScheduleConfigCreateFactory(ModelFactory):
    __model__ = ScheduleConfigCreate

    cron_expression = None
    interval_seconds = 60
    payload = {}
