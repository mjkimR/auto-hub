from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Union
from uuid import UUID

from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.features.scheduling.schedule_configs.models import ScheduleConfig


class ScheduleJobStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"


class ScheduleJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "schedule_jobs"
    __table_args__ = (Index("ix_schedule_jobs_retry_lookup", "status", "retry_need", "retry_attempts"),)
    name: Mapped[str] = mapped_column(index=True)

    schedule_config_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("schedule_configs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Reference to the schedule config that triggered this job execution.",
    )
    dispatcher_run_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Reference to the dispatcher run that executed this job. This allows grouping multiple schedule jobs under a single dispatcher run for better traceability.",
    )
    status: Mapped[str] = mapped_column(
        nullable=False,
        comment="Execution status of the schedule.",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Timestamp when the task execution started.",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Timestamp when the task execution finished.",
    )
    payload: Mapped[dict] = mapped_column(
        JSON_VARIANT,
        nullable=False,
        default={},
        comment="Snapshot of the payload used during execution.",
    )
    error_message: Mapped[str | None] = mapped_column(
        nullable=True,
        comment="Error message if the task execution failed.",
    )

    # retry
    retry_need: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Indicates whether this job needs to be retried. This can be set to True for failed jobs that should be retried by the dispatcher.",
    )
    retry_attempts: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of retry attempts that have been made for this job. This can be used by the dispatcher to implement retry logic with a maximum number of attempts.",
    )
    retry_max: Mapped[int] = mapped_column(
        nullable=False,
        default=3,
        comment="Maximum number of retry attempts allowed for this job. Once retry_attempts reaches this number, the job will no longer be retried.",
    )

    # relationships
    schedule_config: Mapped[Union["ScheduleConfig", None]] = relationship(
        "ScheduleConfig",
        foreign_keys=[schedule_config_id],
        lazy="select",
    )
