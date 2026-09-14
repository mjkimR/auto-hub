from datetime import UTC, datetime, timedelta

import pytest
from app.features.ai_catalogs.models import AICatalog, AICatalogKind, AICatalogState
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.assertions import assert_status_code


@pytest.mark.e2e
class TestAICatalogsAPI:
    _base_url = "/api/v1/ai-catalogs"

    async def test_list_ai_catalogs(self, client: AsyncClient, session: AsyncSession):
        catalog = AICatalog(
            key="test-catalog-list",
            name="Test Catalog List",
            kind=AICatalogKind.CODEX,
            adapter="codex-github-mention",
            enabled=True,
            availability_state=AICatalogState.NORMAL,
            configured_concurrency=3,
            revision=1,
        )
        session.add(catalog)
        await session.commit()

        response = await client.get(self._base_url)
        assert_status_code(response, 200)
        items = response.json()["items"]
        found = next((item for item in items if item["key"] == "test-catalog-list"), None)
        assert found is not None
        assert found["name"] == "Test Catalog List"
        assert found["configured_concurrency"] == 3
        assert found["effective_concurrency"] == 3
        assert found["availability_state"] == "normal"

    async def test_set_and_clear_availability(self, client: AsyncClient, session: AsyncSession):
        catalog = AICatalog(
            key="test-catalog-avail",
            name="Test Catalog Avail",
            kind=AICatalogKind.CODEX,
            adapter="codex-github-mention",
            enabled=True,
            availability_state=AICatalogState.NORMAL,
            revision=1,
        )
        session.add(catalog)
        await session.commit()

        future_time = datetime.now(UTC) + timedelta(hours=2)
        payload = {
            "available_at": future_time.isoformat(),
            "note": "Temporary quota reset hold",
            "source": "manual",
        }

        # Set availability
        response = await client.put(f"{self._base_url}/test-catalog-avail/availability", json=payload)
        assert_status_code(response, 200)
        data = response.json()
        assert data["availability_state"] == "quota_blocked"
        assert data["availability_note"] == "Temporary quota reset hold"
        assert data["availability_source"] == "manual"

        # Past time should be rejected with 422
        past_time = datetime.now(UTC) - timedelta(hours=1)
        response = await client.put(
            f"{self._base_url}/test-catalog-avail/availability",
            json={"available_at": past_time.isoformat()},
        )
        assert_status_code(response, 422)

        # Clear availability
        response = await client.delete(f"{self._base_url}/test-catalog-avail/availability")
        assert_status_code(response, 200)
        cleared = response.json()
        assert cleared["availability_state"] == "normal"
        assert cleared["available_at"] is None
        assert cleared["availability_note"] is None

    async def test_set_enabled(self, client: AsyncClient, session: AsyncSession):
        catalog = AICatalog(
            key="test-catalog-enabled",
            name="Test Catalog Enabled",
            kind=AICatalogKind.CODEX,
            adapter="codex-github-mention",
            enabled=True,
            availability_state=AICatalogState.NORMAL,
            revision=1,
        )
        session.add(catalog)
        await session.commit()

        # Disable
        response = await client.put(f"{self._base_url}/test-catalog-enabled/enabled", json={"enabled": False})
        assert_status_code(response, 200)
        assert response.json()["enabled"] is False
        assert response.json()["availability_state"] == "disabled"

        # Re-enable
        response = await client.put(f"{self._base_url}/test-catalog-enabled/enabled", json={"enabled": True})
        assert_status_code(response, 200)
        assert response.json()["enabled"] is True
        assert response.json()["availability_state"] == "normal"

    async def test_catalog_not_found(self, client: AsyncClient):
        response = await client.put(
            f"{self._base_url}/non-existent/availability",
            json={"available_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
        )
        assert_status_code(response, 404)
        assert "AI catalog not found" in response.json().get("detail", str(response.json()))

        response = await client.delete(f"{self._base_url}/non-existent/availability")
        assert_status_code(response, 404)
        assert "AI catalog not found" in response.json().get("detail", str(response.json()))

        response = await client.put(f"{self._base_url}/non-existent/enabled", json={"enabled": False})
        assert_status_code(response, 404)
        assert "AI catalog not found" in response.json().get("detail", str(response.json()))
