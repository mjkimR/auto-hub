from datetime import UTC, datetime

import pytest
from app.features.scheduling.schedule_jobs.models import ScheduleJob, ScheduleJobStatus
from app.features.scheduling.schedule_jobs.repos import ScheduleJobRepository
from app.features.scheduling.schedule_jobs.services import ScheduleJobContextKwargs
from app.features.scheduling.schedule_jobs.usecases.crud import DeleteScheduleJobUseCase
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestDeleteScheduleJob:
    async def test_delete_schedule_job_success(
        self,
        session: AsyncSession,
        make_db,
    ):
        job: ScheduleJob = await make_db(
            ScheduleJobRepository,
            name="delete_target_job",
            status=ScheduleJobStatus.SUCCESS,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )

        use_case = resolve_dependency(DeleteScheduleJobUseCase)
        context: ScheduleJobContextKwargs = {}

        await use_case.execute(job.id, context=context)

        job_id = job.id
        session.expire_all()
        db_job = await session.get(ScheduleJob, job_id)
        assert db_job is None
