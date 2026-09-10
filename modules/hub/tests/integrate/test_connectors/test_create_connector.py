import pytest
from app.features.connectors.crypto import get_credential_key_provider
from app.features.connectors.models import Connector
from app.features.connectors.schemas import ConnectorCreate, ConnectorProvider
from app.features.connectors.services import ConnectorContextKwargs
from app.features.connectors.usecases.crud import CreateConnectorUseCase
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.fastapi import resolve_dependency


@pytest.mark.integrate
class TestCreateConnector:
    async def test_create_encrypts_credentials_in_database(
        self,
        session: AsyncSession,
        credential_key_provider,
    ):
        use_case = resolve_dependency(
            CreateConnectorUseCase,
            overrides={get_credential_key_provider: credential_key_provider},
        )
        credentials: dict[str, JsonValue] = {"token": "linear-secret-token"}
        connector_in = ConnectorCreate(
            name="linear-production",
            provider=ConnectorProvider.LINEAR,
            config={"workspace_id": "workspace-1"},
            credentials=credentials,
        )

        context: ConnectorContextKwargs = {}
        created = await use_case.execute(connector_in, context=context)

        stored = await session.get(Connector, created.id)
        assert stored is not None
        assert b"linear-secret-token" not in stored.credentials_ciphertext
        assert len(stored.credentials_nonce) == 12
        assert stored.credential_key_version == "test-v1"
        assert await use_case.service.get_credentials(session, stored) == credentials
