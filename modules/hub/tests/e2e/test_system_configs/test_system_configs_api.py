import uuid

import pytest
from app.features.configuration.system_configs.models import SystemConfig
from app.features.configuration.system_configs.repos import SystemConfigRepository
from app.features.configuration.system_configs.schemas import SystemConfigCreate, SystemConfigRead
from httpx import AsyncClient

from tests.utils.assertions import (
    assert_json_contains,
    assert_paginated_response,
    assert_status_code,
)


@pytest.mark.e2e
class TestSystemConfigsAPI:
    _base_url = "/api/v1/system_configs"

    @classmethod
    def base_url(cls, system_config_id=None) -> str:
        url = cls._base_url
        if system_config_id:
            url += f"/{system_config_id}"
        return url

    # -------------------------
    # POST /system_configs
    # -------------------------

    async def test_create_system_config_success(
        self,
        client: AsyncClient,
    ):
        payload = SystemConfigCreate(name="feature_flag", data={"enabled": True, "max_retries": 3})

        response = await client.post(self.base_url(), json=payload.model_dump())

        assert_status_code(response, 201)
        created = SystemConfigRead.model_validate(response.json())
        assert_json_contains(response, {"name": "feature_flag"})
        assert created.data == {"enabled": True, "max_retries": 3}

    async def test_create_system_config_duplicate_name_fails(
        self,
        client: AsyncClient,
        make_db,
    ):
        await make_db(SystemConfigRepository, name="unique_key", data={})

        payload = SystemConfigCreate(name="unique_key", data={"other": "value"})
        response = await client.post(self.base_url(), json=payload.model_dump())

        # Unique constraint violation should return an error status
        assert response.status_code in (409, 422, 500)

    # -------------------------
    # GET /system_configs
    # -------------------------

    async def test_get_system_configs(
        self,
        client: AsyncClient,
        make_db_batch,
    ):
        # Pass data={} to prevent polyfactory from generating non-JSON-serializable types
        await make_db_batch(SystemConfigRepository, 3, data={})

        response = await client.get(self.base_url())

        assert_status_code(response, 200)
        assert_paginated_response(response, min_items=3)

    # -------------------------
    # GET /system_configs/{id}
    # -------------------------

    async def test_get_system_config_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        config: SystemConfig = await make_db(
            SystemConfigRepository,
            name="my_setting",
            data={"value": 42},
        )

        response = await client.get(self.base_url(config.id))

        assert_status_code(response, 200)
        retrieved = SystemConfigRead.model_validate(response.json())
        assert retrieved.id == config.id
        assert retrieved.name == "my_setting"
        assert retrieved.data == {"value": 42}

    async def test_get_system_config_not_found(
        self,
        client: AsyncClient,
    ):
        response = await client.get(self.base_url(uuid.uuid4()))

        assert_status_code(response, 404)

    # -------------------------
    # PATCH /system_configs/{id}
    # -------------------------

    async def test_patch_system_config_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        config: SystemConfig = await make_db(
            SystemConfigRepository,
            name="patch_target",
            data={"old_key": "old_value"},
        )

        response = await client.patch(
            self.base_url(config.id),
            json={"data": {"new_key": "new_value"}},
        )

        assert_status_code(response, 200)
        updated = SystemConfigRead.model_validate(response.json())
        assert updated.data == {"new_key": "new_value"}

    async def test_patch_system_config_not_found(
        self,
        client: AsyncClient,
    ):
        response = await client.patch(
            self.base_url(uuid.uuid4()),
            json={"name": "ghost"},
        )

        assert_status_code(response, 404)

    # -------------------------
    # PUT /system_configs/{id}
    # -------------------------

    async def test_put_system_config_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        config: SystemConfig = await make_db(
            SystemConfigRepository,
            name="put_target",
            data={"old": True},
        )
        put_payload = SystemConfigCreate(name="put_target_renamed", data={"new": True})

        response = await client.put(
            self.base_url(config.id),
            json=put_payload.model_dump(),
        )

        assert_status_code(response, 200)
        updated = SystemConfigRead.model_validate(response.json())
        assert updated.name == "put_target_renamed"
        assert updated.data == {"new": True}

    # -------------------------
    # DELETE /system_configs/{id}
    # -------------------------

    async def test_delete_system_config_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        config: SystemConfig = await make_db(
            SystemConfigRepository,
            name="to_be_deleted",
            data={},
        )

        response = await client.delete(self.base_url(config.id))

        assert_status_code(response, 200)
        response_json = response.json()
        assert "message" in response_json
        assert response_json["identity"] == str(config.id)

        # Verify deletion
        response = await client.get(self.base_url(config.id))
        assert_status_code(response, 404)

    async def test_delete_system_config_not_found(
        self,
        client: AsyncClient,
    ):
        response = await client.delete(self.base_url(uuid.uuid4()))

        assert_status_code(response, 404)
