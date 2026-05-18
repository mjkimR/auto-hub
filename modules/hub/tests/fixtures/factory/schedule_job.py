from app.features.schedule_jobs.models import ScheduleJobStatus
from app.features.schedule_jobs.schemas import ScheduleJobCreate
from polyfactory.factories.pydantic_factory import ModelFactory


class ScheduleJobCreateFactory(ModelFactory):
    __model__ = ScheduleJobCreate

    schedule_config_id = None
    dispatcher_run_id = None
    status = ScheduleJobStatus.PENDING
    finished_at = None
    error_message = None
    payload = {}
