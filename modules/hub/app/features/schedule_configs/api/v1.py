from typing import Annotated
from uuid import UUID

from app.features.schedule_configs.query_options import schedule_config_query_options
from app.features.schedule_configs.schemas import (
    ScheduleConfigCreate,
    ScheduleConfigPatch,
    ScheduleConfigPut,
    ScheduleConfigRead,
)
from app.features.schedule_configs.usecases.crud import (
    CreateScheduleConfigUseCase,
    DeleteScheduleConfigUseCase,
    GetMultiScheduleConfigUseCase,
    GetScheduleConfigUseCase,
    PatchScheduleConfigUseCase,
    PutScheduleConfigUseCase,
)
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/schedule_configs", tags=["ScheduleConfig"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ScheduleConfigRead)
async def create_schedule_config(
    use_case: Annotated[CreateScheduleConfigUseCase, Depends()],
    schedule_config_in: ScheduleConfigCreate,
):
    return await use_case.execute(schedule_config_in)


@router.get("", response_model=PaginatedList[ScheduleConfigRead])
async def get_schedule_configs(
    use_case: Annotated[GetMultiScheduleConfigUseCase, Depends()],
    query_options: Annotated[ListQueryOptions, Depends(schedule_config_query_options)],
):
    return await use_case.execute(query_options)


@router.get("/{schedule_config_id}", response_model=ScheduleConfigRead)
async def get_schedule_config(
    use_case: Annotated[GetScheduleConfigUseCase, Depends()],
    schedule_config_id: UUID,
):
    schedule_config = await use_case.execute(schedule_config_id)
    if not schedule_config:
        raise NotFoundException()
    return schedule_config


@router.patch("/{schedule_config_id}", response_model=ScheduleConfigRead)
async def patch_schedule_config(
    use_case: Annotated[PatchScheduleConfigUseCase, Depends()],
    schedule_config_id: UUID,
    schedule_config_in: ScheduleConfigPatch,
):
    schedule_config = await use_case.execute(schedule_config_id, schedule_config_in)
    if not schedule_config:
        raise NotFoundException()
    return schedule_config


@router.put("/{schedule_config_id}", response_model=ScheduleConfigRead)
async def put_schedule_config(
    use_case: Annotated[PutScheduleConfigUseCase, Depends()],
    schedule_config_id: UUID,
    schedule_config_in: ScheduleConfigPut,
):
    schedule_config = await use_case.execute(schedule_config_id, schedule_config_in)
    if not schedule_config:
        raise NotFoundException()
    return schedule_config


@router.delete("/{schedule_config_id}", response_model=DeleteResponse)
async def delete_schedule_config(
    use_case: Annotated[DeleteScheduleConfigUseCase, Depends()],
    schedule_config_id: UUID,
):
    return await use_case.execute(schedule_config_id)
