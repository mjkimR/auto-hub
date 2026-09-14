import uuid

import pytest
from app.features.connectors.models import Connector
from app.features.connectors.schemas import ConnectorRead
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.assertions import assert_paginated_response, assert_status_code


@pytest.mark.e2e
class TestConnectorsAPI:
    _base_url = "/api/v1/connectors"

    async def test_create_and_read_connector_without_exposing_credentials(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ):
        payload = {
            "name": "github-production",
            "provider": "github",
            "config": {"installation_id": 12345},
            "credentials": {"private_key": "very-secret-private-key"},
        }

        response = await client.post(self._base_url, json=payload)

        assert_status_code(response, 201)
        created = ConnectorRead.model_validate(response.json())
        assert created.has_credentials is True
        assert "credentials" not in response.json()
        assert "credentials_ciphertext" not in response.json()

        stored = await session.get(Connector, created.id)
        assert stored is not None
        assert b"very-secret-private-key" not in stored.credentials_ciphertext

        response = await client.get(f"{self._base_url}/{created.id}")
        assert_status_code(response, 200)
        assert "credentials" not in response.json()

    async def test_list_filter_update_and_delete_connector(self, client: AsyncClient):
        create_response = await client.post(
            self._base_url,
            json={
                "name": "github-secondary",
                "provider": "github",
                "config": {"installation_id": 67890},
                "credentials": {"refresh_token": "old-token"},
            },
        )
        assert_status_code(create_response, 201)
        connector_id = create_response.json()["id"]

        response = await client.get(self._base_url, params={"provider": "github"})
        assert_status_code(response, 200)
        assert_paginated_response(response, min_items=1)

        response = await client.patch(
            f"{self._base_url}/{connector_id}",
            json={"enabled": False, "credentials": {"refresh_token": "new-token"}},
        )
        assert_status_code(response, 200)
        assert response.json()["enabled"] is False

        response = await client.delete(f"{self._base_url}/{connector_id}")
        assert_status_code(response, 200)
        assert response.json()["identity"] == connector_id

        response = await client.get(f"{self._base_url}/{connector_id}")
        assert_status_code(response, 404)

    async def test_unsupported_provider_is_rejected(self, client: AsyncClient):
        response = await client.post(
            self._base_url,
            json={"name": "gitlab-production", "provider": "gitlab", "credentials": {"token": "secret"}},
        )
        assert_status_code(response, 422)

    async def test_get_connector_not_found(self, client: AsyncClient):
        response = await client.get(f"{self._base_url}/{uuid.uuid4()}")
        assert_status_code(response, 404)
