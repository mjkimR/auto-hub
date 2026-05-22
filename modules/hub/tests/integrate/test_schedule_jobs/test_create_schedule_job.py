from datetime import UTC, datetime

import pytest
from app.features.schedule_configs.repos import ScheduleConfigRepository
from app.features.schedule_jobs.models import ScheduleJob, ScheduleJobStatus
from app.features.schedule_jobs.schemas import ScheduleJobCreate
from app.features.schedule_jobs.services import ScheduleJobContextKwargs
from app.features.schedule_jobs.usecases.crud import CreateScheduleJobUseCase
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestCreateScheduleJob:
    async def test_create_schedule_job_success(
        self,
        session: AsyncSession,
        make_db,
    ):
        config = await make_db(
            ScheduleConfigRepository,
            name="job_parent_config",
            task_func="tasks.example_task",
            interval_seconds=60,
        )

        use_case = resolve_dependency(CreateScheduleJobUseCase)
        context: ScheduleJobContextKwargs = {}

        now = datetime.now(UTC)
        job_in = ScheduleJobCreate(
            name="test_job",
            schedule_config_id=config.id,
            status=ScheduleJobStatus.PENDING,
            started_at=now,
        )

        created = await use_case.execute(job_in, context=context)

        assert created.name == "test_job"
        assert created.schedule_config_id == config.id
        assert created.status == ScheduleJobStatus.PENDING
        assert created.error_message is None

        db_job = await session.get(ScheduleJob, created.id)
        assert db_job is not None
        assert db_job.name == "test_job"

    async def test_create_schedule_job_without_config(
        self,
        session: AsyncSession,
    ):
        use_case = resolve_dependency(CreateScheduleJobUseCase)
        context: ScheduleJobContextKwargs = {}

        now = datetime.now(UTC)
        job_in = ScheduleJobCreate(
            name="orphan_job",
            schedule_config_id=None,
            status=ScheduleJobStatus.PENDING,
            started_at=now,
        )

        created = await use_case.execute(job_in, context=context)

        assert created.name == "orphan_job"
        assert created.schedule_config_id is None

        db_job = await session.get(ScheduleJob, created.id)
        assert db_job is not None

    async def test_create_schedule_job_failure_status(
        self,
        session: AsyncSession,
    ):
        use_case = resolve_dependency(CreateScheduleJobUseCase)
        context: ScheduleJobContextKwargs = {}

        now = datetime.now(UTC)
        job_in = ScheduleJobCreate(
            name="failed_job",
            schedule_config_id=None,
            status=ScheduleJobStatus.FAILURE,
            started_at=now,
            finished_at=now,
            error_message="Something went wrong",
        )

        created = await use_case.execute(job_in, context=context)

        assert created.status == ScheduleJobStatus.FAILURE
        assert created.error_message == "Something went wrong"
        assert created.finished_at is not None
