from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class SchedulerDefaults(BaseSettings):
    GLOBAL_TIMEOUT_SECONDS: int = Field(300, description="Default global timeout for scheduled tasks in seconds")
    GLOBAL_TIMEOUT_BUFFER: int = Field(
        30,
        description="Buffer time to subtract from the global timeout to ensure tasks complete within limits in seconds",
    )
    MAX_CONCURRENT_TASKS: int = Field(10, description="Maximum number of concurrent tasks that can be scheduled")
    MAX_RETRY_ATTEMPTS: int = Field(3, description="Maximum number of retry attempts for failed tasks")
    MAX_DISPATCH_LIMIT: int = Field(
        200, description="Maximum number of schedules or retry jobs to fetch in a single tick"
    )

    @property
    def effective_timeout(self) -> int:
        """Calculate the effective timeout by subtracting the buffer from the global timeout."""
        if self.GLOBAL_TIMEOUT_BUFFER >= self.GLOBAL_TIMEOUT_SECONDS:
            raise ValueError("GLOBAL_TIMEOUT_BUFFER must be less than GLOBAL_TIMEOUT_SECONDS")
        return self.GLOBAL_TIMEOUT_SECONDS - self.GLOBAL_TIMEOUT_BUFFER


@lru_cache
def get_scheduler_defaults() -> SchedulerDefaults:
    """Get an instance of SchedulerDefaults with values loaded from environment variables or defaults."""
    return SchedulerDefaults(**{})
