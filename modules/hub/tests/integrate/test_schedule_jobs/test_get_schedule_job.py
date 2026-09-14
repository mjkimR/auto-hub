from datetime import UTC, datetime

import pytest
from app.features.scheduling.schedule_jobs.models import ScheduleJob, ScheduleJobStatus
from app.features.scheduling.schedule_jobs.repos import ScheduleJobRepository
from app.features.scheduling.schedule_jobs.schemas import ScheduleJobCreate
from app.features.scheduling.schedule_jobs.services import ScheduleJobContextKwargs, ScheduleJobService
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestGetScheduleJob:
    async def test_get_schedule_job_success(
        self,
        session: AsyncSession,
    ):
        repo = resolve_dependency(ScheduleJobRepository)
        job: ScheduleJob = await repo.create(
            session,
            obj_in=ScheduleJobCreate(
                name="get_test_job",
                status=ScheduleJobStatus.SUCCESS,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            ),
        )

        service = resolve_dependency(ScheduleJobService)
        context: ScheduleJobContextKwargs = {}

        retrieved = await service.get(session, job.id, context=context)

        assert retrieved is not None
        assert retrieved.id == job.id
        assert retrieved.name == "get_test_job"
        assert retrieved.status == ScheduleJobStatus.SUCCESS

    async def test_get_multi_schedule_jobs(
        self,
        session: AsyncSession,
    ):
        repo = resolve_dependency(ScheduleJobRepository)
        now = datetime.now(UTC)
        for i in range(3):
            await repo.create(
                session,
                obj_in=ScheduleJobCreate(
                    name=f"multi_job_{i}",
                    status=ScheduleJobStatus.PENDING,
                    started_at=now,
                ),
            )

        service = resolve_dependency(ScheduleJobService)
        context: ScheduleJobContextKwargs = {}

        results = await service.get_multi(session, context=context)

        assert len(results.items) == 3
