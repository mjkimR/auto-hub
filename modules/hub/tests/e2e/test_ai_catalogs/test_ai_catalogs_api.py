from datetime import UTC, datetime, timedelta

import pytest
from app.features.ai_catalogs.models import AICatalog, AICatalogKind, AICatalogSession, AICatalogState
from app.features.configuration.connectors.models import Connector
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.assertions import assert_status_code


def catalog(key: str, kind: str = AICatalogKind.CODEX, **fields) -> AICatalog:
    return AICatalog(
        key=key,
        name=key.replace("-", " ").title(),
        kind=kind,
        adapter="jules-api" if kind == AICatalogKind.JULES else "codex-github-mention",
        enabled=True,
        availability_state=AICatalogState.NORMAL,
        revision=1,
        **fields,
    )


def connector(name: str, provider: str) -> Connector:
    return Connector(
        name=name,
        provider=provider,
        config={},
        enabled=True,
        credentials_ciphertext=b"sealed",
        credentials_nonce=b"0" * 12,
        credential_key_version="test",
    )


@pytest.mark.e2e
class TestAICatalogsAPI:
    _base_url = "/api/v1/ai-catalogs"

    async def test_list_ai_catalogs(self, client: AsyncClient, session: AsyncSession):
        session.add(catalog("test-catalog-list", configured_concurrency=3))
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
        assert found["policy_config"] == {}
        assert found["pipeline_delivery"] is True
        assert found["connector_provider"] is None

    async def test_set_and_clear_availability(self, client: AsyncClient, session: AsyncSession):
        session.add(catalog("test-catalog-avail"))
        await session.commit()

        future_time = datetime.now(UTC) + timedelta(hours=2)
        payload = {
            "available_at": future_time.isoformat(),
            "note": "Temporary quota reset hold",
            "source": "manual",
        }

        response = await client.put(f"{self._base_url}/test-catalog-avail/availability", json=payload)
        assert_status_code(response, 200)
        data = response.json()
        assert data["availability_state"] == "quota_blocked"
        assert data["availability_note"] == "Temporary quota reset hold"
        assert data["availability_source"] == "manual"

        past_time = datetime.now(UTC) - timedelta(hours=1)
        response = await client.put(
            f"{self._base_url}/test-catalog-avail/availability",
            json={"available_at": past_time.isoformat()},
        )
        assert_status_code(response, 422)

        response = await client.delete(f"{self._base_url}/test-catalog-avail/availability")
        assert_status_code(response, 200)
        cleared = response.json()
        assert cleared["availability_state"] == "normal"
        assert cleared["available_at"] is None
        assert cleared["availability_note"] is None

    async def test_set_enabled(self, client: AsyncClient, session: AsyncSession):
        session.add(catalog("test-catalog-enabled"))
        await session.commit()

        response = await client.put(f"{self._base_url}/test-catalog-enabled/enabled", json={"enabled": False})
        assert_status_code(response, 200)
        assert response.json()["enabled"] is False
        assert response.json()["availability_state"] == "disabled"

        response = await client.put(f"{self._base_url}/test-catalog-enabled/enabled", json={"enabled": True})
        assert_status_code(response, 200)
        assert response.json()["enabled"] is True
        assert response.json()["availability_state"] == "normal"

    async def test_update_codex_refresh_policy_through_policy_config(self, client: AsyncClient, session: AsyncSession):
        session.add(catalog("test-catalog-policy"))
        await session.commit()

        response = await client.put(
            f"{self._base_url}/test-catalog-policy/policy-config",
            json={
                "policy_config": {
                    "short_refresh_enabled": False,
                    "short_refresh_cycle_minutes": 240,
                    "long_refresh_cycle_minutes": 20_160,
                }
            },
        )
        assert_status_code(response, 200)
        data = response.json()
        assert data["policy_config"] == {
            "short_refresh_enabled": False,
            "short_refresh_cycle_minutes": 240,
            "long_refresh_cycle_minutes": 20_160,
            "probe_window_minutes": 10,
        }
        assert data["refresh_jitter_minutes"] == 10

        response = await client.put(
            f"{self._base_url}/test-catalog-policy/policy-config",
            json={"policy_config": {"short_refresh_enabled": True, "short_refresh_cycle_minutes": 0}},
        )
        assert_status_code(response, 422)

    async def test_update_policy_config_is_validated_by_the_kind(self, client: AsyncClient, session: AsyncSession):
        session.add_all(
            [
                catalog("test-catalog-jules", AICatalogKind.JULES, configured_concurrency=15),
                catalog("test-catalog-codex-config"),
            ]
        )
        await session.commit()

        response = await client.put(
            f"{self._base_url}/test-catalog-jules/policy-config",
            json={"policy_config": {"daily_task_limit": 100, "window": "calendar", "timezone": "Asia/Seoul"}},
        )
        assert_status_code(response, 200)
        assert response.json()["policy_config"] == {
            "daily_task_limit": 100,
            "window": "calendar",
            "timezone": "Asia/Seoul",
        }
        assert response.json()["effective_concurrency"] == 15

        response = await client.put(
            f"{self._base_url}/test-catalog-jules/policy-config", json={"policy_config": {"daily_task_limit": 0}}
        )
        assert_status_code(response, 422)

        response = await client.put(
            f"{self._base_url}/test-catalog-codex-config/policy-config",
            json={"policy_config": {"daily_task_limit": 100}},
        )
        assert_status_code(response, 422)

    async def test_set_connector_accepts_only_the_kinds_provider(self, client: AsyncClient, session: AsyncSession):
        jules_connector, github_connector = connector("jules-key", "jules"), connector("github-key", "github")
        session.add_all(
            [
                catalog("test-catalog-jules-connector", AICatalogKind.JULES),
                catalog("test-catalog-codex-connector"),
                jules_connector,
                github_connector,
            ]
        )
        await session.flush()
        jules_id, github_id = str(jules_connector.id), str(github_connector.id)
        await session.commit()
        url = f"{self._base_url}/test-catalog-jules-connector/connector"

        response = await client.put(url, json={"connector_id": jules_id})
        assert_status_code(response, 200)
        assert response.json()["connector_id"] == jules_id

        assert_status_code(await client.put(url, json={"connector_id": github_id}), 422)
        assert_status_code(
            await client.put(
                f"{self._base_url}/test-catalog-codex-connector/connector", json={"connector_id": jules_id}
            ),
            422,
        )

        response = await client.put(url, json={"connector_id": None})
        assert_status_code(response, 200)
        assert response.json()["connector_id"] is None

    async def test_lists_sessions_and_counts_open_ones(self, client: AsyncClient, session: AsyncSession):
        jules = catalog("test-catalog-sessions", AICatalogKind.JULES)
        session.add(jules)
        await session.flush()
        session.add_all(
            [
                AICatalogSession(
                    ai_catalog_id=jules.id,
                    title="Hygiene [hub-session:a]",
                    state="completed",
                    pull_request_url="https://github.com/owner/app/pull/1",
                ),
                AICatalogSession(
                    ai_catalog_id=jules.id,
                    title="Report [hub-session:b]",
                    state="in_progress",
                    url="https://jules.google/session/2",
                ),
                AICatalogSession(ai_catalog_id=jules.id, title="Audit [hub-session:c]", state="failed"),
            ]
        )
        await session.commit()
        url = f"{self._base_url}/test-catalog-sessions/sessions"

        first = await client.get(url, params={"offset": 0, "limit": 2})
        second = await client.get(url, params={"offset": 2, "limit": 2})
        assert_status_code(first, 200)
        assert_status_code(second, 200)
        assert (first.json()["total_count"], second.json()["total_count"]) == (3, 3)
        assert (len(first.json()["items"]), len(second.json()["items"])) == (2, 1)
        # Pages never overlap or skip a session, even when sessions share a creation time.
        titles = [item["title"] for item in first.json()["items"] + second.json()["items"]]
        assert sorted(titles) == ["Audit [hub-session:c]", "Hygiene [hub-session:a]", "Report [hub-session:b]"]
        assert_status_code(await client.get(url, params={"limit": 101}), 422)

        listing = next(
            item
            for item in (await client.get(self._base_url)).json()["items"]
            if item["key"] == "test-catalog-sessions"
        )
        assert listing["connector_provider"] == "jules"
        assert listing["pipeline_delivery"] is False
        assert (listing["open_session_count"], listing["active_dispatch_count"]) == (1, 1)

        assert_status_code(await client.get(f"{self._base_url}/non-existent/sessions"), 404)

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
