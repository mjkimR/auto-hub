from app.features.configuration.connectors.models import Connector
from app.features.configuration.connectors.schemas import ConnectorCreate, ConnectorPatch, ConnectorPut
from app_layer_base.base.repos.base import BaseRepository


class ConnectorRepository(BaseRepository[Connector, ConnectorCreate, ConnectorPut, ConnectorPatch]):
    model = Connector
