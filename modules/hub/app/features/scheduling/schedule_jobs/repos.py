from app.features.scheduling.schedule_jobs.models import ScheduleJob
from app.features.scheduling.schedule_jobs.schemas import ScheduleJobCreate, ScheduleJobPatch, ScheduleJobPut
from app_layer_base.base.repos.base import BaseRepository


class ScheduleJobRepository(BaseRepository[ScheduleJob, ScheduleJobCreate, ScheduleJobPut, ScheduleJobPatch]):
    model = ScheduleJob
