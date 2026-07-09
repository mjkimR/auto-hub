from datetime import datetime
from uuid import UUID

from app.features.schedule_jobs.models import ScheduleJobStatus
from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class ScheduleJobBase(BaseModel):
    name: str = Field(description="The name of the schedule job.")
    schedule_config_id: UUID | None = Field(
        default=None,
        description="Reference to the schedule config that triggered this job execution.",
    )
    dispatcher_run_id: UUID | None = Field(
        default=None,
        description="Reference to the dispatcher run that executed this job. Allows grouping multiple schedule jobs under a single dispatcher run for better traceability.",
    )
    status: ScheduleJobStatus = Field(description="Execution status of the schedule.")
    started_at: datetime = Field(description="Timestamp when the task execution started.")
    finished_at: datetime | None = Field(
        default=None,
        description="Timestamp when the task execution finished.",
    )
    payload: dict = Field(default_factory=dict, description="Snapshot of the payload used during execution.")
    error_message: str | None = Field(default=None, description="Error message if the task execution failed.")


class ScheduleJobCreate(ScheduleJobBase):
    pass


class ScheduleJobPut(ScheduleJobBase):
    pass


class ScheduleJobPatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the schedule job.")
    schedule_config_id: UUID | None = Field(default=None, description="Reference to the schedule config.")
    dispatcher_run_id: UUID | None = Field(default=None, description="Reference to the dispatcher run.")
    status: ScheduleJobStatus | None = Field(default=None, description="Execution status of the schedule.")
    started_at: datetime | None = Field(default=None, description="Timestamp when the task execution started.")
    finished_at: datetime | None = Field(default=None, description="Timestamp when the task execution finished.")
    payload: dict | None = Field(default=None, description="Snapshot of the payload used during execution.")
    error_message: str | None = Field(default=None, description="Error message if the task execution failed.")


class ScheduleJobRead(UUIDSchemaMixin, TimestampSchemaMixin, ScheduleJobBase):
    model_config = ConfigDict(from_attributes=True)
