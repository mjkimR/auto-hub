import functools
from datetime import datetime

from app_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from croniter import CroniterBadCronError, croniter
from pydantic import BaseModel, ConfigDict, Field, model_validator


@functools.lru_cache(maxsize=1024)
def _check_cron_expression(cron_expression: str) -> str | None:
    """Validate cron expression and return an error message if invalid, or None if valid.

    By returning None on success and the error message string on failure, this helper
    ensures that both valid and invalid expressions are cached by lru_cache, avoiding
    unnecessary parsing overhead during repeated validations.
    """
    try:
        croniter(cron_expression)
        return None
    except (CroniterBadCronError, ValueError) as e:
        return str(e)


def _validate_cron_expression(cron_expression: str) -> None:
    """Validate a cron expression and raise a ValueError if invalid.

    Delegates to the cached helper _check_cron_expression to ensure validation results
    are fetched from the cache when possible.
    """
    error_msg = _check_cron_expression(cron_expression)
    if error_msg is not None:
        raise ValueError(f"Invalid cron_expression: {error_msg}")


class ScheduleConfigBase(BaseModel):
    name: str = Field(description="Human-readable name of the schedule.")
    description: str | None = Field(default=None, description="Optional description of what this schedule does.")

    task_func: str = Field(description="Dotted path to the task function to execute (e.g. 'tasks.send_report').")
    cron_expression: str | None = Field(
        default=None,
        description="Cron expression for time-based scheduling (e.g. '0 9 * * 1-5'). Mutually exclusive with interval_seconds.",
    )
    interval_seconds: int | None = Field(
        default=None,
        description="Fixed interval in seconds between executions. Mutually exclusive with cron_expression.",
    )
    payload: dict = Field(default={}, description="Arbitrary JSON payload passed to the task function as kwargs.")
    enabled: bool = Field(
        default=True, description="Whether this schedule is active and should be picked up by the dispatcher."
    )
    start_at: datetime | None = Field(
        default=None, description="Optional datetime after which the schedule becomes active."
    )
    end_at: datetime | None = Field(
        default=None, description="Optional datetime after which the schedule is no longer executed."
    )

    @model_validator(mode="after")
    def validate_trigger(self) -> "ScheduleConfigBase":
        if self.cron_expression is None and self.interval_seconds is None:
            raise ValueError("Either cron_expression or interval_seconds must be provided.")
        if self.cron_expression is not None and self.interval_seconds is not None:
            raise ValueError("cron_expression and interval_seconds are mutually exclusive.")
        if self.cron_expression is not None:
            _validate_cron_expression(self.cron_expression)
        return self


class ScheduleConfigCreate(ScheduleConfigBase):
    pass


class ScheduleConfigPut(ScheduleConfigBase):
    pass


class ScheduleConfigPatch(BaseModel):
    name: str | None = Field(default=None, description="Human-readable name of the schedule.")
    description: str | None = Field(default=None, description="Optional description of what this schedule does.")
    task_func: str | None = Field(default=None, description="Dotted path to the task function to execute.")
    cron_expression: str | None = Field(default=None, description="Cron expression for time-based scheduling.")
    interval_seconds: int | None = Field(default=None, description="Fixed interval in seconds between executions.")
    payload: dict | None = Field(
        default=None, description="Arbitrary JSON payload passed to the task function as kwargs."
    )
    enabled: bool | None = Field(default=None, description="Whether this schedule is active.")
    start_at: datetime | None = Field(
        default=None, description="Optional datetime after which the schedule becomes active."
    )
    end_at: datetime | None = Field(
        default=None, description="Optional datetime after which the schedule is no longer executed."
    )

    @model_validator(mode="after")
    def validate_trigger(self) -> "ScheduleConfigPatch":
        if self.cron_expression is not None and self.interval_seconds is not None:
            raise ValueError("cron_expression and interval_seconds are mutually exclusive.")
        if self.cron_expression is not None:
            _validate_cron_expression(self.cron_expression)
        return self


class ScheduleConfigRead(UUIDSchemaMixin, TimestampSchemaMixin, ScheduleConfigBase):
    last_run_at: datetime | None = Field(description="Timestamp of the most recent execution.")
    next_run_at: datetime | None = Field(description="Timestamp of the next scheduled execution.")
    model_config = ConfigDict(from_attributes=True)
