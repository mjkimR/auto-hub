"""Integration tests for dispatching the real example tasks (hello_world, no_payload_task).

Unlike other dispatcher tests that mock task_registry, these tests verify
that the actual tasks registered via @task() decorator are correctly
discovered and executed end-to-end through DispatcherService.dispatch_jobs.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

# Ensure hello_world is registered in task_registry before tests run
import app.features.tasks.examples  # noqa: F401
import pytest
import pytest_asyncio
from app.common.config import SchedulerDefaults
from app.features.dispatchers.services import DispatcherService
from app.features.schedule_configs.models import ScheduleConfig
from app.features.schedule_configs.schemas import ScheduleConfigRead
from app.features.schedule_jobs.models import ScheduleJob, ScheduleJobStatus
from app.features.schedule_jobs.repos import ScheduleJobRepository
from app.features.schedule_jobs.schemas import ScheduleJobRead
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def settings() -> SchedulerDefaults:
    return SchedulerDefaults(
        GLOBAL_TIMEOUT_SECONDS=60,
        GLOBAL_TIMEOUT_BUFFER=10,
        MAX_CONCURRENT_TASKS=5,
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
    config = ScheduleConfig(
        name=kwargs.get("name", f"cfg-{uuid.uuid4().hex[:6]}"),
        task_func=kwargs.get("task_func", "hello_world"),
        cron_expression=kwargs.get("cron_expression", None),
        interval_seconds=kwargs.get("interval_seconds", 60),
        payload=kwargs.get("payload", {}),
        enabled=kwargs.get("enabled", True),
        start_at=kwargs.get("start_at", None),
        end_at=kwargs.get("end_at", None),
        next_run_at=kwargs.get("next_run_at", None),
        last_run_at=kwargs.get("last_run_at", None),
    )
    session.add(config)
    await session.flush()
    await session.refresh(config)
    return config


async def _create_schedule_job(session: AsyncSession, config: ScheduleConfig, **kwargs) -> ScheduleJob:
    job = ScheduleJob(
        name=config.name,
        schedule_config_id=config.id,
        dispatcher_run_id=uuid.uuid4(),
        status=kwargs.get("status", ScheduleJobStatus.PENDING),
        started_at=kwargs.get("started_at", NOW - timedelta(minutes=1)),
        finished_at=kwargs.get("finished_at", None),
        payload=kwargs.get("payload", {}),
        error_message=kwargs.get("error_message", None),
        retry_need=kwargs.get("retry_need", False),
        retry_attempts=kwargs.get("retry_attempts", 0),
        retry_max=kwargs.get("retry_max", 3),
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


# ---------------------------------------------------------------------------
# TestExampleTaskDispatch
# ---------------------------------------------------------------------------


@pytest.mark.real_commit
class TestExampleTaskDispatch:
    """Integration tests that dispatch the real hello_world example task."""

    @pytest_asyncio.fixture
    async def hello_world_job(self, session) -> tuple:
        """Creates a ScheduleConfig + ScheduleJob wired to the real hello_world task."""
        config = await _create_schedule_config(
            session,
            name="hello-world-config",
            task_func="hello_world",
        )
        job_obj = await _create_schedule_job(session, config, status=ScheduleJobStatus.PENDING)
        await session.commit()
        await session.refresh(job_obj)
        await session.refresh(config)

        job_dto = ScheduleJobRead.model_validate(job_obj)
        config_dto = ScheduleConfigRead.model_validate(config)
        return job_obj, job_dto, config_dto, job_dto.dispatcher_run_id

    @pytest_asyncio.fixture
    async def hello_world_job_with_message(self, session) -> tuple:
        """Creates a ScheduleConfig + ScheduleJob with a custom message payload."""
        config = await _create_schedule_config(
            session,
            name="hello-world-msg-config",
            task_func="hello_world",
            payload={"message": "integration test"},
        )
        job_obj = await _create_schedule_job(
            session,
            config,
            status=ScheduleJobStatus.PENDING,
            payload={"message": "integration test"},
        )
        await session.commit()
        await session.refresh(job_obj)
        await session.refresh(config)

        job_dto = ScheduleJobRead.model_validate(job_obj)
        config_dto = ScheduleConfigRead.model_validate(config)
        return job_obj, job_dto, config_dto, job_dto.dispatcher_run_id

    async def test_hello_world_task_completes_with_success_status(self, service, session, hello_world_job):
        """hello_world task should run successfully without mocking and set job status to SUCCESS."""
        job_obj, job_dto, config_dto, run_id = hello_world_job

        await service.dispatch_jobs([(job_dto, config_dto)], run_id)

        session.expire_all()
        result = await session.execute(select(ScheduleJob).where(ScheduleJob.id == job_dto.id))
        updated = result.scalar_one()

        assert updated.status == ScheduleJobStatus.SUCCESS
        assert updated.finished_at is not None
        assert updated.error_message is None
        assert updated.retry_need is False

    async def test_hello_world_task_with_custom_message_payload(self, service, session, hello_world_job_with_message):
        """hello_world task should accept a custom message payload and still succeed."""
        job_obj, job_dto, config_dto, run_id = hello_world_job_with_message

        await service.dispatch_jobs([(job_dto, config_dto)], run_id)

        session.expire_all()
        result = await session.execute(select(ScheduleJob).where(ScheduleJob.id == job_dto.id))
        updated = result.scalar_one()

        assert updated.status == ScheduleJobStatus.SUCCESS
        assert updated.finished_at is not None
        assert updated.error_message is None

    async def test_hello_world_task_is_registered_in_task_registry(self):
        """hello_world should be discoverable in task_registry by name."""
        from app.features import tasks as task_registry

        func = task_registry.get("hello_world")
        assert func is not None
        assert callable(func)
        assert func.__name__ == "hello_world"

    async def test_hello_world_multiple_concurrent_dispatches(self, service, session):
        """Multiple hello_world jobs should all complete successfully when dispatched concurrently."""
        pairs = []
        job_ids = []

        for i in range(3):
            config = await _create_schedule_config(
                session,
                name=f"hello-world-multi-{i}",
                task_func="hello_world",
                payload={"message": f"msg-{i}"},
            )
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

        await service.dispatch_jobs(pairs, run_id)

        session.expire_all()
        result = await session.execute(select(ScheduleJob).where(ScheduleJob.id.in_(job_ids)))
        jobs = result.scalars().all()

        assert len(jobs) == 3
        assert all(j.status == ScheduleJobStatus.SUCCESS for j in jobs)
        assert all(j.finished_at is not None for j in jobs)
        assert all(j.error_message is None for j in jobs)


# ---------------------------------------------------------------------------
# TestNoPayloadTaskDispatch
# ---------------------------------------------------------------------------


class TestNoPayloadTaskDispatch:
    """Integration tests that dispatch the real no_payload_task example task."""

    @pytest_asyncio.fixture
    async def no_payload_job(self, session) -> tuple:
        """Creates a ScheduleConfig + ScheduleJob wired to the real no_payload_task."""
        config = await _create_schedule_config(
            session,
            name="no-payload-config",
            task_func="no_payload_task",
        )
        job_obj = await _create_schedule_job(session, config, status=ScheduleJobStatus.PENDING)
        await session.commit()
        await session.refresh(job_obj)
        await session.refresh(config)

        job_dto = ScheduleJobRead.model_validate(job_obj)
        config_dto = ScheduleConfigRead.model_validate(config)
        return job_obj, job_dto, config_dto, job_dto.dispatcher_run_id

    async def test_no_payload_task_completes_with_success_status(self, service, session, no_payload_job):
        """no_payload_task should run successfully and set job status to SUCCESS."""
        job_obj, job_dto, config_dto, run_id = no_payload_job

        await service.dispatch_jobs([(job_dto, config_dto)], run_id)

        session.expire_all()
        result = await session.execute(select(ScheduleJob).where(ScheduleJob.id == job_dto.id))
        updated = result.scalar_one()

        assert updated.status == ScheduleJobStatus.SUCCESS
        assert updated.finished_at is not None
        assert updated.error_message is None
        assert updated.retry_need is False

    async def test_no_payload_task_is_registered_in_task_registry(self):
        """no_payload_task should be discoverable in task_registry by name."""
        from app.features import tasks as task_registry

        func = task_registry.get("no_payload_task")
        assert func is not None
        assert callable(func)
        assert func.__name__ == "no_payload_task"
