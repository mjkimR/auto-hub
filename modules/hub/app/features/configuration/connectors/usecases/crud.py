from typing import Annotated

from app.features.configuration.connectors.models import Connector
from app.features.configuration.connectors.schemas import ConnectorCreate, ConnectorPatch, ConnectorPut
from app.features.configuration.connectors.services import ConnectorContextKwargs, ConnectorService
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends


class GetConnectorUseCase(BaseGetUseCase[ConnectorService, Connector, ConnectorContextKwargs]):
    def __init__(self, service: Annotated[ConnectorService, Depends()]) -> None:
        super().__init__(service)


class GetMultiConnectorUseCase(BaseGetMultiUseCase[ConnectorService, Connector, ConnectorContextKwargs]):
    def __init__(self, service: Annotated[ConnectorService, Depends()]) -> None:
        super().__init__(service)


class CreateConnectorUseCase(BaseCreateUseCase[ConnectorService, Connector, ConnectorCreate, ConnectorContextKwargs]):
    def __init__(self, service: Annotated[ConnectorService, Depends()]) -> None:
        super().__init__(service)


class PatchConnectorUseCase(
    BasePatchUseCase[ConnectorService, Connector, ConnectorPut, ConnectorPatch, ConnectorContextKwargs]
):
    def __init__(self, service: Annotated[ConnectorService, Depends()]) -> None:
        super().__init__(service)


class PutConnectorUseCase(
    BasePutUseCase[ConnectorService, Connector, ConnectorPut, ConnectorPatch, ConnectorContextKwargs]
):
    def __init__(self, service: Annotated[ConnectorService, Depends()]) -> None:
        super().__init__(service)


class DeleteConnectorUseCase(BaseDeleteUseCase[ConnectorService, Connector, ConnectorContextKwargs]):
    def __init__(self, service: Annotated[ConnectorService, Depends()]) -> None:
        super().__init__(service)
