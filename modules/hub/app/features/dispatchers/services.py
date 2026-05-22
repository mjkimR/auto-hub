import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from inspect import iscoroutinefunction
from typing import Annotated
from uuid import UUID

from app.common.config import SchedulerDefaults, get_scheduler_defaults
from app.common.utils.calc_schedule import calc_next_run as _calc_next_run_util
from app.features import tasks as task_registry
from app.features.schedule_configs.models import ScheduleConfig
from app.features.schedule_configs.schemas import ScheduleConfigRead
from app.features.schedule_jobs.models import ScheduleJob, ScheduleJobStatus
from app.features.schedule_jobs.repos import ScheduleJobRepository
from app.features.schedule_jobs.schemas import ScheduleJobRead
from app.features.tasks.core.context import task_context
from app_base.core.database.transaction import AsyncTransaction
from app_base.core.log import logger
from app_base.core.traceback import get_exception_traceback_str
from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import func as sql_func


class DispatcherService:
    """Service responsible for dispatching scheduled jobs based on their configurations.

    Manages concurrency via a semaphore and applies a global timeout across all
    dispatched tasks within a single tick.
    """

    def __init__(
        self,
        job_repo: Annotated[ScheduleJobRepository, Depends()],
        settings: SchedulerDefaults | None = None,
    ) -> None:
        """Initialize the DispatcherService.

        Args:
            job_repo: Repository for managing ScheduleJob persistence.
            settings: Optional scheduler defaults; falls back to the global defaults if not provided.
        """
        if settings is None:
            settings = get_scheduler_defaults()
        self.settings = settings
        self.global_timeout = settings.effective_timeout
        self.job_repo = job_repo
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_TASKS)

    @classmethod
    def calc_next_run(cls, config: ScheduleConfig, now: datetime) -> datetime:
        """Calculate the next run time for a schedule config.

        Delegates to :func:`app.common.utils.calc_schedule.calc_next_run`.

        Args:
            config: The schedule configuration whose next run time is being calculated.
            now: The reference datetime (typically UTC now).

        Returns:
            The next datetime at which the schedule should run.

        Raises:
            ValueError: If the config has neither a cron expression nor an interval.
        """
        return _calc_next_run_util(config.cron_expression, config.interval_seconds, now)

    async def get_schedule_configs(self, session: AsyncSession, now: datetime) -> Sequence[ScheduleConfig]:
        """Fetch all enabled schedule configs that are due to run.

        Uses SELECT FOR UPDATE SKIP LOCKED to prevent concurrent workers from
        picking up the same configs simultaneously.

        A config is considered due when all of the following conditions are met:

        - ``enabled`` is True.
        - ``next_run_at`` is NULL (meaning it has never run and should be executed
          immediately on the first dispatch tick) **or** ``next_run_at <= now``.
        - ``start_at`` is NULL or has already passed.
        - ``end_at`` is NULL or has not yet passed.

        .. note::
            ``next_run_at = NULL`` is the sentinel value that signals *"execute me immediately"*.
            After the first execution the dispatcher sets ``next_run_at`` to the calculated
            future datetime (via :meth:`calc_next_run`) so the config is no longer selected
            on every subsequent tick.

        Args:
            session: The active async database session.
            now: The current UTC datetime used to evaluate due conditions.

        Returns:
            A sequence of ScheduleConfig instances that are ready to be dispatched.
        """
        stmt = (
            select(ScheduleConfig)
            .where(
                ScheduleConfig.enabled.is_(True),
                (ScheduleConfig.next_run_at.is_(None)) | (ScheduleConfig.next_run_at <= now),
                (ScheduleConfig.start_at.is_(None)) | (ScheduleConfig.start_at <= now),
                (ScheduleConfig.end_at.is_(None)) | (ScheduleConfig.end_at >= now),
            )
            .limit(self.settings.MAX_DISPATCH_LIMIT)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        due_configs = result.scalars().all()
        return due_configs

    async def get_retry_jobs(self, session: AsyncSession, current_config_ids: Sequence[UUID]) -> Sequence[ScheduleJob]:
        """Fetch jobs that need to be retried, excluding those whose config is currently running.

        If a job's schedule_config is already in current_config_ids (meaning it is being
        dispatched in the current tick), we bypass the retry for that job and reset its
        retry_need flag to False, as a new execution is already taking place.

        For jobs not in current_config_ids, if retry_need is True and retry_attempts
        is less than retry_max, they are selected for retry.

        Args:
            session: The active async database session.
            current_config_ids: Sequence of ScheduleConfig UUIDs that are running in this tick.

        Returns:
            A sequence of ScheduleJob instances ready to be retried.
        """
        if current_config_ids:
            # 1. Reset retry_need to False for jobs that belong to configs currently being executed.
            update_stmt = (
                update(ScheduleJob)
                .where(
                    ScheduleJob.status == ScheduleJobStatus.FAILURE,
                    ScheduleJob.retry_need.is_(True),
                    ScheduleJob.schedule_config_id.in_(current_config_ids),
                )
                .values(retry_need=False)
            )
            await session.execute(update_stmt)

        # 2. Fetch the actual retry candidates using FOR UPDATE SKIP LOCKED.
        stmt = (
            select(ScheduleJob)
            .where(
                ScheduleJob.status == ScheduleJobStatus.FAILURE,
                ScheduleJob.retry_need.is_(True),
                ScheduleJob.retry_attempts < ScheduleJob.retry_max,
            )
            .options(selectinload(ScheduleJob.schedule_config))
            .limit(self.settings.MAX_DISPATCH_LIMIT)
            .with_for_update(skip_locked=True)
        )

        # Explicitly exclude the current_config_ids from the fetch (though the update above technically clears their retry_need anyway)
        if current_config_ids:
            stmt = stmt.where(ScheduleJob.schedule_config_id.notin_(current_config_ids))

        result = await session.execute(stmt)
        return result.scalars().all()

    async def dispatch_jobs(self, jobs: list[tuple[ScheduleJobRead, ScheduleConfigRead]], run_id: UUID) -> None:
        """Dispatch a batch of schedule jobs concurrently with a global timeout.

        All jobs are gathered concurrently. If the entire batch exceeds the global
        timeout, a timeout error is logged and remaining tasks are cancelled.

        Args:
            jobs: A list of (ScheduleJobRead, ScheduleConfigRead) tuples to dispatch.
            run_id: The UUID of the dispatcher run for traceability.
        """
        try:
            await asyncio.wait_for(
                asyncio.gather(*[self._dispatch(job, config, run_id=run_id) for job, config in jobs]),
                timeout=self.global_timeout,
            )
        except TimeoutError:
            logger.error(
                f"tick() gather timed out after {self.global_timeout}s",
            )

    async def _dispatch(self, job: ScheduleJobRead, config: ScheduleConfigRead, run_id: UUID) -> None:
        """Acquire the concurrency semaphore and delegate to _run_dispatch.

        Args:
            job: The persisted job record associated with this dispatch.
            config: The schedule configuration that triggered this job.
            run_id: The UUID of the dispatcher run for traceability.
        """
        async with self._semaphore:
            await self._run_dispatch(job, config, run_id=run_id)

    async def _run_dispatch(self, job: ScheduleJobRead, config: ScheduleConfigRead, run_id: UUID) -> None:
        """Execute the task function associated with a schedule config and record the result.

        Looks up the task function from the task registry, invokes it (supporting both
        async and sync callables), then updates the corresponding ScheduleJob record
        with the final status, finish time, and any error message.

        Args:
            job: The persisted job record to be updated after execution.
            config: The schedule configuration providing the task function and payload.
            run_id: The UUID of the dispatcher run for traceability.
        """
        with task_context(config_id=config.id, config_name=config.name, run_id=run_id):
            error_message: str | None = None
            is_cancelled = False
            retry_need = False
            status = ScheduleJobStatus.SUCCESS
            short_id = str(config.id).split("-")[0]
            prefix = f"[sch:{config.name}|{short_id}]"

            try:
                task_fn = task_registry.get(config.task_func)
                if task_fn is None:
                    raise ValueError(f"Task function '{config.task_func}' is not registered in task_registry.")
                if iscoroutinefunction(task_fn):
                    await task_fn(payload=config.payload)
                else:
                    raise TypeError(f"Task function '{config.task_func}' must be an async function.")
                logger.debug(f"{prefix} Dispatched schedule")
            except TimeoutError:
                status = ScheduleJobStatus.FAILURE
                error_message = f"Task timed out after {self.global_timeout}s"
                logger.error(f"{prefix} timed out individually")
                retry_need = True
            except asyncio.CancelledError:
                status = ScheduleJobStatus.FAILURE
                error_message = "Task was cancelled (likely due to app shutdown or outer timeout)"
                logger.warning(f"{prefix} cancelled")
                is_cancelled = True
                retry_need = True
            except Exception as e:
                status = ScheduleJobStatus.FAILURE
                error_message = str(e)
                error_trace = get_exception_traceback_str(e)
                logger.error(f"{prefix} failed: {e}\n{error_trace}")

            finished_at = datetime.now(UTC)

            # Update schedule job
            async with AsyncTransaction() as session:
                update_stmt = (
                    update(ScheduleJob)
                    .where(ScheduleJob.id == job.id)
                    .values(
                        status=status,
                        finished_at=finished_at,
                        error_message=error_message,
                        retry_need=retry_need,
                        retry_attempts=sql_func.coalesce(ScheduleJob.retry_attempts, 0) + 1,
                    )
                )
                result = await session.execute(update_stmt)
                await session.commit()
                if result.rowcount == 0:  # type: ignore
                    logger.error(f"{prefix} Failed to update ScheduleJob - not found")

            if is_cancelled:
                raise asyncio.CancelledError  # Reraise
