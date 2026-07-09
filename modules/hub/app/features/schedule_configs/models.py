from datetime import datetime

from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column


class ScheduleConfig(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "schedule_configs"
    __table_args__ = (Index("ix_schedule_configs_enabled_next_run_at", "enabled", "next_run_at"),)
    name: Mapped[str] = mapped_column(index=True, comment="Human-readable name of the schedule")
    description: Mapped[str | None] = mapped_column(
        nullable=True, comment="Optional description of what this schedule does"
    )

    task_func: Mapped[str] = mapped_column(
        nullable=False, index=True, comment="Dotted path to the task function to execute (e.g. 'tasks.send_report')"
    )
    cron_expression: Mapped[str | None] = mapped_column(
        nullable=True,
        comment="Cron expression for time-based scheduling (e.g. '0 9 * * 1-5'). Mutually exclusive with interval_seconds",
    )
    interval_seconds: Mapped[int | None] = mapped_column(
        nullable=True, comment="Fixed interval in seconds between executions. Mutually exclusive with cron_expression"
    )
    payload: Mapped[dict] = mapped_column(
        JSON_VARIANT, nullable=False, default={}, comment="Arbitrary JSON payload passed to the task function as kwargs"
    )

    enabled: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment="Whether this schedule is active and should be picked up by the dispatcher",
    )
    start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Optional datetime after which the schedule becomes active"
    )
    end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Optional datetime after which the schedule is no longer executed",
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, comment="Timestamp of the most recent execution"
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Timestamp of the next scheduled execution. NULL indicates this schedule should be executed immediately by the dispatcher.",
    )
