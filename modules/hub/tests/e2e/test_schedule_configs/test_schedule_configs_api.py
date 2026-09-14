import uuid

import pytest
from app.features.scheduling.schedule_configs.models import ScheduleConfig
from app.features.scheduling.schedule_configs.repos import ScheduleConfigRepository
from app.features.scheduling.schedule_configs.schemas import ScheduleConfigCreate, ScheduleConfigRead
from httpx import AsyncClient

from tests.utils.assertions import (
    assert_json_contains,
    assert_paginated_response,
    assert_status_code,
)


@pytest.mark.e2e
class TestScheduleConfigsAPI:
    _base_url = "/api/v1/schedule_configs"

    @classmethod
    def base_url(cls, schedule_config_id=None) -> str:
        url = cls._base_url
        if schedule_config_id:
            url += f"/{schedule_config_id}"
        return url

    # -------------------------
    # POST /schedule_configs
    # -------------------------

    async def test_create_schedule_config_with_interval_success(
        self,
        client: AsyncClient,
    ):
        payload = ScheduleConfigCreate(
            name="My Interval Schedule",
            task_func="tasks.example",
            interval_seconds=60,
        )

        response = await client.post(self.base_url(), json=payload.model_dump())

        assert_status_code(response, 201)
        created = ScheduleConfigRead.model_validate(response.json())
        assert_json_contains(response, {"name": "My Interval Schedule", "interval_seconds": 60})
        assert created.task_func == "tasks.example"
        assert created.enabled is True

    async def test_create_schedule_config_with_cron_success(
        self,
        client: AsyncClient,
    ):
        payload = ScheduleConfigCreate(
            name="My Cron Schedule",
            task_func="tasks.example",
            cron_expression="0 9 * * 1-5",
        )

        response = await client.post(self.base_url(), json=payload.model_dump())

        assert_status_code(response, 201)
        created = ScheduleConfigRead.model_validate(response.json())
        assert created.cron_expression == "0 9 * * 1-5"

    async def test_create_schedule_config_without_trigger_fails(
        self,
        client: AsyncClient,
    ):
        payload = {
            "name": "No Trigger",
            "task_func": "tasks.example",
        }

        response = await client.post(self.base_url(), json=payload)

        assert_status_code(response, 422)

    async def test_create_schedule_config_with_both_triggers_fails(
        self,
        client: AsyncClient,
    ):
        payload = {
            "name": "Both Triggers",
            "task_func": "tasks.example",
            "cron_expression": "0 9 * * *",
            "interval_seconds": 60,
        }

        response = await client.post(self.base_url(), json=payload)

        assert_status_code(response, 422)

    # -------------------------
    # GET /schedule_configs
    # -------------------------

    async def test_get_schedule_configs(
        self,
        client: AsyncClient,
        make_db_batch,
    ):
        await make_db_batch(ScheduleConfigRepository, 3, interval_seconds=60)

        response = await client.get(self.base_url())

        assert_status_code(response, 200)
        assert_paginated_response(response, min_items=3)

    # -------------------------
    # GET /schedule_configs/{id}
    # -------------------------

    async def test_get_schedule_config_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            name="Get This Config",
            task_func="tasks.example",
            interval_seconds=120,
        )

        response = await client.get(self.base_url(config.id))

        assert_status_code(response, 200)
        retrieved = ScheduleConfigRead.model_validate(response.json())
        assert retrieved.id == config.id
        assert retrieved.name == "Get This Config"

    # -------------------------
    # PATCH /schedule_configs/{id}
    # -------------------------

    async def test_patch_schedule_config_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            name="Old Name",
            task_func="tasks.example",
            interval_seconds=60,
        )

        response = await client.patch(
            self.base_url(config.id),
            json={"name": "New Name", "enabled": False},
        )

        assert_status_code(response, 200)
        updated = ScheduleConfigRead.model_validate(response.json())
        assert updated.name == "New Name"
        assert updated.enabled is False

    async def test_patch_schedule_config_not_found(
        self,
        client: AsyncClient,
    ):
        response = await client.patch(
            self.base_url(uuid.uuid4()),
            json={"name": "Ghost"},
        )

        assert_status_code(response, 404)

    # -------------------------
    # PUT /schedule_configs/{id}
    # -------------------------

    async def test_put_schedule_config_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            name="Original",
            task_func="tasks.example",
            interval_seconds=60,
        )
        put_payload = ScheduleConfigCreate(
            name="Replaced",
            task_func="tasks.updated",
            cron_expression="*/5 * * * *",
        )

        response = await client.put(
            self.base_url(config.id),
            json=put_payload.model_dump(),
        )

        assert_status_code(response, 200)
        updated = ScheduleConfigRead.model_validate(response.json())
        assert updated.name == "Replaced"
        assert updated.task_func == "tasks.updated"
        assert updated.cron_expression == "*/5 * * * *"
        assert updated.interval_seconds is None

    # -------------------------
    # DELETE /schedule_configs/{id}
    # -------------------------

    async def test_delete_schedule_config_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            name="To Be Deleted",
            task_func="tasks.example",
            interval_seconds=60,
        )

        response = await client.delete(self.base_url(config.id))

        assert_status_code(response, 200)
        response_json = response.json()
        assert "message" in response_json
        assert response_json["identity"] == str(config.id)

        # Verify deletion
        response = await client.get(self.base_url(config.id))
        assert_status_code(response, 404)

    async def test_delete_schedule_config_not_found(
        self,
        client: AsyncClient,
    ):
        response = await client.delete(self.base_url(uuid.uuid4()))

        assert_status_code(response, 404)
