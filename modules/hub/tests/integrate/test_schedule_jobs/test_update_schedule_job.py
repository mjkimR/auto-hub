from datetime import UTC, datetime

import pytest
from app.features.schedule_jobs.models import ScheduleJob, ScheduleJobStatus
from app.features.schedule_jobs.repos import ScheduleJobRepository
from app.features.schedule_jobs.schemas import ScheduleJobPatch, ScheduleJobPut
from app.features.schedule_jobs.services import ScheduleJobContextKwargs
from app.features.schedule_jobs.usecases.crud import PatchScheduleJobUseCase, PutScheduleJobUseCase
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestUpdateScheduleJob:
    async def test_put_schedule_job_success(
        self,
        session: AsyncSession,
        make_db,
    ):
        now = datetime.now(UTC)
        job: ScheduleJob = await make_db(
            ScheduleJobRepository,
            name="put_target_job",
            status=ScheduleJobStatus.PENDING,
            started_at=now,
            finished_at=None,
        )

        use_case = resolve_dependency(PutScheduleJobUseCase)
        context: ScheduleJobContextKwargs = {}

        update_data = ScheduleJobPut(
            name="put_target_job",
            status=ScheduleJobStatus.SUCCESS,
            started_at=now,
            finished_at=now,
        )
        updated = await use_case.execute(job.id, update_data, context=context)

        assert updated is not None
        assert updated.id == job.id
        assert updated.status == ScheduleJobStatus.SUCCESS
        assert updated.finished_at is not None

        await session.refresh(job)
        assert job.status == ScheduleJobStatus.SUCCESS

    async def test_patch_schedule_job_status_to_failure(
        self,
        session: AsyncSession,
        make_db,
    ):
        now = datetime.now(UTC)
        job: ScheduleJob = await make_db(
            ScheduleJobRepository,
            name="patch_target_job",
            status=ScheduleJobStatus.PENDING,
            started_at=now,
            finished_at=None,
        )

        use_case = resolve_dependency(PatchScheduleJobUseCase)
        context: ScheduleJobContextKwargs = {}

        patch_data = ScheduleJobPatch(
            status=ScheduleJobStatus.FAILURE,
            finished_at=now,
            error_message="Task timed out",
        )
        patched = await use_case.execute(job.id, patch_data, context=context)

        assert patched is not None
        assert patched.id == job.id
        assert patched.status == ScheduleJobStatus.FAILURE
        assert patched.error_message == "Task timed out"

        await session.refresh(job)
        assert job.status == ScheduleJobStatus.FAILURE
        assert job.error_message == "Task timed out"

    async def test_patch_schedule_job_name(
        self,
        session: AsyncSession,
        make_db,
    ):
        now = datetime.now(UTC)
        job: ScheduleJob = await make_db(
            ScheduleJobRepository,
            name="old_job_name",
            status=ScheduleJobStatus.PENDING,
            started_at=now,
            finished_at=None,
        )

        use_case = resolve_dependency(PatchScheduleJobUseCase)
        context: ScheduleJobContextKwargs = {}

        patched = await use_case.execute(job.id, ScheduleJobPatch(name="new_job_name"), context=context)

        assert patched is not None
        assert patched.name == "new_job_name"

        await session.refresh(job)
        assert job.name == "new_job_name"
