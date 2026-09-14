from typing import Annotated
from uuid import UUID

from app.features.configuration.connectors.query_options import connector_query_options
from app.features.configuration.connectors.schemas import ConnectorCreate, ConnectorPatch, ConnectorPut, ConnectorRead
from app.features.configuration.connectors.usecases.crud import (
    CreateConnectorUseCase,
    DeleteConnectorUseCase,
    GetConnectorUseCase,
    GetMultiConnectorUseCase,
    PatchConnectorUseCase,
    PutConnectorUseCase,
)
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/connectors", tags=["Connector"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ConnectorRead)
async def create_connector(
    use_case: Annotated[CreateConnectorUseCase, Depends()],
    connector_in: ConnectorCreate,
):
    return await use_case.execute(connector_in)


@router.get("", response_model=PaginatedList[ConnectorRead])
async def get_connectors(
    use_case: Annotated[GetMultiConnectorUseCase, Depends()],
    query_options: Annotated[ListQueryOptions, Depends(connector_query_options)],
):
    return await use_case.execute(query_options)


@router.get("/{connector_id}", response_model=ConnectorRead)
async def get_connector(
    use_case: Annotated[GetConnectorUseCase, Depends()],
    connector_id: UUID,
):
    connector = await use_case.execute(connector_id)
    if not connector:
        raise NotFoundException()
    return connector


@router.patch("/{connector_id}", response_model=ConnectorRead)
async def patch_connector(
    use_case: Annotated[PatchConnectorUseCase, Depends()],
    connector_id: UUID,
    connector_in: ConnectorPatch,
):
    connector = await use_case.execute(connector_id, connector_in)
    if not connector:
        raise NotFoundException()
    return connector


@router.put("/{connector_id}", response_model=ConnectorRead)
async def put_connector(
    use_case: Annotated[PutConnectorUseCase, Depends()],
    connector_id: UUID,
    connector_in: ConnectorPut,
):
    connector = await use_case.execute(connector_id, connector_in)
    if not connector:
        raise NotFoundException()
    return connector


@router.delete("/{connector_id}", response_model=DeleteResponse)
async def delete_connector(
    use_case: Annotated[DeleteConnectorUseCase, Depends()],
    connector_id: UUID,
):
    return await use_case.execute(connector_id)
