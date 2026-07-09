from app.features.schedule_jobs.models import ScheduleJob
from app.features.schedule_jobs.schemas import ScheduleJobCreate, ScheduleJobPatch, ScheduleJobPut
from app_layer_base.base.repos.base import BaseRepository


class ScheduleJobRepository(BaseRepository[ScheduleJob, ScheduleJobCreate, ScheduleJobPut, ScheduleJobPatch]):
    model = ScheduleJob
