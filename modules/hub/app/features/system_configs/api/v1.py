from typing import Annotated
from uuid import UUID

from app.features.system_configs.query_options import system_config_query_options
from app.features.system_configs.schemas import SystemConfigCreate, SystemConfigPatch, SystemConfigPut, SystemConfigRead
from app.features.system_configs.usecases.crud import (
    CreateSystemConfigUseCase,
    DeleteSystemConfigUseCase,
    GetMultiSystemConfigUseCase,
    GetSystemConfigUseCase,
    PatchSystemConfigUseCase,
    PutSystemConfigUseCase,
)
from app_base.base.exceptions.basic import NotFoundException
from app_base.base.repos.query_options import ListQueryOptions
from app_base.base.schemas.delete_resp import DeleteResponse
from app_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/system_configs", tags=["SystemConfig"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SystemConfigRead)
async def create_system_config(
    use_case: Annotated[CreateSystemConfigUseCase, Depends()],
    system_config_in: SystemConfigCreate,
):
    return await use_case.execute(system_config_in)


@router.get("", response_model=PaginatedList[SystemConfigRead])
async def get_system_configs(
    use_case: Annotated[GetMultiSystemConfigUseCase, Depends()],
    query_options: Annotated[ListQueryOptions, Depends(system_config_query_options)],
):
    return await use_case.execute(query_options)


@router.get("/{system_config_id}", response_model=SystemConfigRead)
async def get_system_config(
    use_case: Annotated[GetSystemConfigUseCase, Depends()],
    system_config_id: UUID,
):
    system_config = await use_case.execute(system_config_id)
    if not system_config:
        raise NotFoundException()
    return system_config


@router.patch("/{system_config_id}", response_model=SystemConfigRead)
async def patch_system_config(
    use_case: Annotated[PatchSystemConfigUseCase, Depends()],
    system_config_id: UUID,
    system_config_in: SystemConfigPatch,
):
    system_config = await use_case.execute(system_config_id, system_config_in)
    if not system_config:
        raise NotFoundException()
    return system_config


@router.put("/{system_config_id}", response_model=SystemConfigRead)
async def put_system_config(
    use_case: Annotated[PutSystemConfigUseCase, Depends()],
    system_config_id: UUID,
    system_config_in: SystemConfigPut,
):
    system_config = await use_case.execute(system_config_id, system_config_in)
    if not system_config:
        raise NotFoundException()
    return system_config


@router.delete("/{system_config_id}", response_model=DeleteResponse)
async def delete_system_config(
    use_case: Annotated[DeleteSystemConfigUseCase, Depends()],
    system_config_id: UUID,
):
    return await use_case.execute(system_config_id)
