from typing import Annotated
from uuid import UUID

from app.features.schedule_jobs.schemas import ScheduleJobCreate, ScheduleJobPatch, ScheduleJobPut, ScheduleJobRead
from app.features.schedule_jobs.usecases.crud import (
    CreateScheduleJobUseCase,
    DeleteScheduleJobUseCase,
    GetMultiScheduleJobUseCase,
    GetScheduleJobUseCase,
    PatchScheduleJobUseCase,
    PutScheduleJobUseCase,
)
from app_base.base.deps.params.page import PaginationParam
from app_base.base.exceptions.basic import NotFoundException
from app_base.base.repos.query_options import ListQueryOptions
from app_base.base.schemas.delete_resp import DeleteResponse
from app_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/schedule_jobs", tags=["ScheduleJob"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ScheduleJobRead)
async def create_schedule_job(
    use_case: Annotated[CreateScheduleJobUseCase, Depends()],
    schedule_job_in: ScheduleJobCreate,
):
    return await use_case.execute(schedule_job_in)


@router.get("", response_model=PaginatedList[ScheduleJobRead])
async def get_schedule_jobs(
    use_case: Annotated[GetMultiScheduleJobUseCase, Depends()],
    pagination: PaginationParam,
):
    return await use_case.execute(ListQueryOptions(offset=pagination.offset, limit=pagination.limit))


@router.get("/{schedule_job_id}", response_model=ScheduleJobRead)
async def get_schedule_job(
    use_case: Annotated[GetScheduleJobUseCase, Depends()],
    schedule_job_id: UUID,
):
    schedule_job = await use_case.execute(schedule_job_id)
    if not schedule_job:
        raise NotFoundException()
    return schedule_job


@router.patch("/{schedule_job_id}", response_model=ScheduleJobRead)
async def patch_schedule_job(
    use_case: Annotated[PatchScheduleJobUseCase, Depends()],
    schedule_job_id: UUID,
    schedule_job_in: ScheduleJobPatch,
):
    schedule_job = await use_case.execute(schedule_job_id, schedule_job_in)
    if not schedule_job:
        raise NotFoundException()
    return schedule_job


@router.put("/{schedule_job_id}", response_model=ScheduleJobRead)
async def put_schedule_job(
    use_case: Annotated[PutScheduleJobUseCase, Depends()],
    schedule_job_id: UUID,
    schedule_job_in: ScheduleJobPut,
):
    schedule_job = await use_case.execute(schedule_job_id, schedule_job_in)
    if not schedule_job:
        raise NotFoundException()
    return schedule_job


@router.delete("/{schedule_job_id}", response_model=DeleteResponse)
async def delete_schedule_job(
    use_case: Annotated[DeleteScheduleJobUseCase, Depends()],
    schedule_job_id: UUID,
):
    return await use_case.execute(schedule_job_id)
