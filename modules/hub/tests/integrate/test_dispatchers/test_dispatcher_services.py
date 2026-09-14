"""Integration tests for DispatcherService.

Tests run against a real (in-memory SQLite) database to verify that
get_schedule_configs, get_retry_jobs, and dispatch_jobs interact correctly
with actual ORM models and transactions.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from app.common.config import SchedulerDefaults
from app.features.execution.dispatchers.services import DispatcherService
from app.features.scheduling.schedule_configs.models import ScheduleConfig
from app.features.scheduling.schedule_jobs.models import ScheduleJob, ScheduleJobStatus
from app.features.scheduling.schedule_jobs.repos import ScheduleJobRepository
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def settings() -> SchedulerDefaults:
    return SchedulerDefaults(
        GLOBAL_TIMEOUT_SECONDS=60,
        GLOBAL_TIMEOUT_BUFFER=10,
        MAX_CONCURRENT_TASKS=5,
        MAX_RETRY_ATTEMPTS=3,
        MAX_DISPATCH_LIMIT=3,
    )


@pytest.fixture
def service(settings) -> DispatcherService:
    svc = DispatcherService.__new__(DispatcherService)
    svc.settings = settings
    svc.global_timeout = settings.effective_timeout
    svc.job_repo = ScheduleJobRepository()
    svc._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_TASKS)
    return svc


async def _create_schedule_config(session: AsyncSession, **kwargs) -> ScheduleConfig:
    """Helper to insert a ScheduleConfig directly into the DB."""
    config = ScheduleConfig(
        name=kwargs.get("name", f"cfg-{uuid.uuid4().hex[:6]}"),
        task_func=kwargs.get("task_func", "hello_world"),
        cron_expression=kwargs.get("cron_expression"),
        interval_seconds=kwargs.get("interval_seconds", 60),
        payload=kwargs.get("payload", {}),
        enabled=kwargs.get("enabled", True),
        start_at=kwargs.get("start_at"),
        end_at=kwargs.get("end_at"),
        next_run_at=kwargs.get("next_run_at"),
        last_run_at=kwargs.get("last_run_at"),
    )
    session.add(config)
    await session.flush()
    await session.refresh(config)
    return config


async def _create_schedule_job(session: AsyncSession, config: ScheduleConfig, **kwargs) -> ScheduleJob:
    """Helper to insert a ScheduleJob directly into the DB."""
    job = ScheduleJob(
        name=config.name,
        schedule_config_id=config.id,
        dispatcher_run_id=uuid.uuid4(),
        status=kwargs.get("status", ScheduleJobStatus.FAILURE),
        started_at=kwargs.get("started_at", NOW - timedelta(minutes=5)),
        finished_at=kwargs.get("finished_at", NOW - timedelta(minutes=4)),
        payload=kwargs.get("payload", {}),
        error_message=kwargs.get("error_message", "some error"),
        retry_need=kwargs.get("retry_need", False),
        retry_attempts=kwargs.get("retry_attempts", 0),
        retry_max=kwargs.get("retry_max", 3),
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


# ---------------------------------------------------------------------------
# TestGetScheduleConfigs
# ---------------------------------------------------------------------------


class TestGetScheduleConfigs:
    """Integration tests for DispatcherService.get_schedule_configs."""

    async def test_returns_due_config(self, service, session):
        """Should return an enabled config whose next_run_at is before now."""
        await _create_schedule_config(session, next_run_at=NOW - timedelta(minutes=1))
        await session.commit()

        result = await service.get_schedule_configs(session, now=NOW)

        assert len(result) == 1

    async def test_returns_config_with_null_next_run_at(self, service, session):
        """A config with next_run_at=None should be treated as immediately due."""
        await _create_schedule_config(session, next_run_at=None)
        await session.commit()

        result = await service.get_schedule_configs(session, now=NOW)

        assert len(result) == 1

    async def test_skips_future_next_run_at(self, service, session):
        """Should not return a config whose next_run_at is in the future."""
        await _create_schedule_config(session, next_run_at=NOW + timedelta(minutes=5))
        await session.commit()

        result = await service.get_schedule_configs(session, now=NOW)

        assert len(result) == 0

    async def test_skips_disabled_config(self, service, session):
        """Should not return a config with enabled=False."""
        await _create_schedule_config(session, enabled=False, next_run_at=NOW - timedelta(minutes=1))
        await session.commit()

        result = await service.get_schedule_configs(session, now=NOW)

        assert len(result) == 0

    async def test_skips_config_before_start_at(self, service, session):
        """Should not return a config whose start_at has not yet been reached."""
        await _create_schedule_config(
            session,
            next_run_at=NOW - timedelta(minutes=1),
            start_at=NOW + timedelta(hours=1),
        )
        await session.commit()

        result = await service.get_schedule_configs(session, now=NOW)

        assert len(result) == 0

    async def test_skips_config_after_end_at(self, service, session):
        """Should not return a config whose end_at has already passed."""
        await _create_schedule_config(
            session,
            next_run_at=NOW - timedelta(minutes=1),
            end_at=NOW - timedelta(seconds=1),
        )
        await session.commit()

        result = await service.get_schedule_configs(session, now=NOW)

        assert len(result) == 0

    async def test_returns_multiple_due_configs(self, service, session):
        """Should return all due configs when multiple exist."""
        for i in range(3):
            await _create_schedule_config(session, name=f"cfg-{i}", next_run_at=NOW - timedelta(minutes=i + 1))
        await session.commit()

        result = await service.get_schedule_configs(session, now=NOW)

        assert len(result) == 3


# ---------------------------------------------------------------------------
# TestGetRetryJobs
# ---------------------------------------------------------------------------


class TestGetRetryJobs:
    """Integration tests for DispatcherService.get_retry_jobs."""

    async def test_returns_retry_candidate(self, service, session):
        """Should return a FAILURE job with retry_need=True and retry_attempts < retry_max."""
        config = await _create_schedule_config(session)
        await _create_schedule_job(
            session, config, status=ScheduleJobStatus.FAILURE, retry_need=True, retry_attempts=0, retry_max=3
        )
        await session.commit()

        result = await service.get_retry_jobs(session, [])

        assert len(result) == 1

    async def test_skips_job_when_retry_need_is_false(self, service, session):
        """Should not return a job with retry_need=False."""
        config = await _create_schedule_config(session)
        await _create_schedule_job(session, config, status=ScheduleJobStatus.FAILURE, retry_need=False)
        await session.commit()

        result = await service.get_retry_jobs(session, [])

        assert len(result) == 0

    async def test_skips_job_when_max_attempts_reached(self, service, session):
        """Should not return a job when retry_attempts >= retry_max."""
        config = await _create_schedule_config(session)
        await _create_schedule_job(
            session, config, status=ScheduleJobStatus.FAILURE, retry_need=True, retry_attempts=3, retry_max=3
        )
        await session.commit()

        result = await service.get_retry_jobs(session, [])

        assert len(result) == 0

    async def test_skips_success_job(self, service, session):
        """Should not return a job with SUCCESS status."""
        config = await _create_schedule_config(session)
        await _create_schedule_job(session, config, status=ScheduleJobStatus.SUCCESS, retry_need=True)
        await session.commit()

        result = await service.get_retry_jobs(session, [])

        assert len(result) == 0

    async def test_resets_retry_need_for_currently_running_config(self, service, session):
        """retry_need of a job belonging to a currently running config_id should be reset to False."""
        config = await _create_schedule_config(session)
        job = await _create_schedule_job(
            session, config, status=ScheduleJobStatus.FAILURE, retry_need=True, retry_attempts=0, retry_max=3
        )
        await session.commit()

        # Excluded because the config is running in the current tick
        result = await service.get_retry_jobs(session, [config.id])
        await session.commit()

        assert len(result) == 0
        await session.refresh(job)
        assert job.retry_need is False

    async def test_returns_job_not_in_current_config_ids(self, service, session):
        """A retry job for a config not in current_config_ids should be returned normally."""
        config_a = await _create_schedule_config(session, name="cfg-a")
        config_b = await _create_schedule_config(session, name="cfg-b")
        await _create_schedule_job(
            session, config_a, status=ScheduleJobStatus.FAILURE, retry_need=True, retry_attempts=0, retry_max=3
        )
        await _create_schedule_job(
            session, config_b, status=ScheduleJobStatus.FAILURE, retry_need=True, retry_attempts=0, retry_max=3
        )
        await session.commit()

        # Only config_a is currently running
        result = await service.get_retry_jobs(session, [config_a.id])

        assert len(result) == 1
        assert result[0].schedule_config_id == config_b.id


# ---------------------------------------------------------------------------
# TestDispatchJobs
# ---------------------------------------------------------------------------


@pytest.mark.real_commit
class TestDispatchJobs:
    """Integration tests for DispatcherService.dispatch_jobs.

    Verifies that task execution results are correctly reflected in
    the actual ScheduleJob records in the DB.
    """

    @pytest_asyncio.fixture
    async def config_and_job(self, session) -> tuple:
        config = await _create_schedule_config(session, task_func="hello_world")
        from app.features.scheduling.schedule_configs.schemas import ScheduleConfigRead
        from app.features.scheduling.schedule_jobs.schemas import ScheduleJobRead

        job_obj = await _create_schedule_job(session, config, status=ScheduleJobStatus.PENDING, retry_need=False)
        await session.commit()
        await session.refresh(job_obj)
        await session.refresh(config)

        job_dto = ScheduleJobRead.model_validate(job_obj)
        config_dto = ScheduleConfigRead.model_validate(config)
        run_id = job_dto.dispatcher_run_id

        return job_obj, job_dto, config_dto, run_id

    async def test_successful_task_updates_job_to_success(self, service, session, config_and_job):
        """On task success, the ScheduleJob status should be updated to SUCCESS."""
        from sqlalchemy import select

        _job_obj, job_dto, config_dto, run_id = config_and_job

        async def _mock_hello_world(**kwargs):
            pass

        with patch("app.features.execution.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _mock_hello_world
            await service.dispatch_jobs([(job_dto, config_dto)], run_id)

        session.expire_all()
        result = await session.execute(select(ScheduleJob).where(ScheduleJob.id == job_dto.id))
        updated = result.scalar_one()

        assert updated.status == ScheduleJobStatus.SUCCESS
        assert updated.finished_at is not None
        assert updated.error_message is None

    async def test_failing_task_updates_job_to_failure(self, service, session, config_and_job):
        """On task failure, the ScheduleJob status should be FAILURE and error_message should be set."""
        from sqlalchemy import select

        _job_obj, job_dto, config_dto, run_id = config_and_job

        async def _mock_failing(**kwargs):
            raise RuntimeError("boom")

        with patch("app.features.execution.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _mock_failing
            await service.dispatch_jobs([(job_dto, config_dto)], run_id)

        session.expire_all()
        result = await session.execute(select(ScheduleJob).where(ScheduleJob.id == job_dto.id))
        updated = result.scalar_one()

        assert updated.status == ScheduleJobStatus.FAILURE
        assert (
            updated.error_message
            == f"An unexpected error occurred during task execution. Please refer to Request ID: {run_id} for details."
        )
        assert updated.retry_need is False

    async def test_multiple_jobs_dispatched_concurrently(self, service, session):
        """Multiple jobs should be dispatched concurrently and all updated to SUCCESS."""
        from app.features.scheduling.schedule_configs.schemas import ScheduleConfigRead
        from app.features.scheduling.schedule_jobs.schemas import ScheduleJobRead
        from sqlalchemy import select

        pairs = []
        job_ids = []
        for i in range(3):
            config = await _create_schedule_config(session, name=f"multi-{i}", task_func="hello_world")
            job_obj = await _create_schedule_job(session, config, status=ScheduleJobStatus.PENDING)
            await session.flush()
            job_ids.append(job_obj.id)
            pairs.append(
                (
                    ScheduleJobRead.model_validate(job_obj),
                    ScheduleConfigRead.model_validate(config),
                )
            )
        await session.commit()
        run_id = uuid.uuid4()

        async def _noop(**kwargs):
            pass

        with patch("app.features.execution.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _noop
            await service.dispatch_jobs(pairs, run_id)

        session.expire_all()
        result = await session.execute(select(ScheduleJob).where(ScheduleJob.id.in_(job_ids)))
        jobs = result.scalars().all()

        assert all(j.status == ScheduleJobStatus.SUCCESS for j in jobs)
