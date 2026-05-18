import uuid
from datetime import datetime, timezone

import pytest
from app.features.schedule_configs.models import ScheduleConfig
from app.features.schedule_configs.repos import ScheduleConfigRepository
from app.features.schedule_jobs.models import ScheduleJob, ScheduleJobStatus
from app.features.schedule_jobs.repos import ScheduleJobRepository
from app.features.schedule_jobs.schemas import ScheduleJobCreate, ScheduleJobRead
from httpx import AsyncClient

from tests.utils.assertions import (
    assert_json_contains,
    assert_paginated_response,
    assert_status_code,
)


@pytest.mark.e2e
class TestScheduleJobsAPI:
    _base_url = "/api/v1/schedule_jobs"

    @classmethod
    def base_url(cls, schedule_job_id=None) -> str:
        url = cls._base_url
        if schedule_job_id:
            url += f"/{schedule_job_id}"
        return url

    # -------------------------
    # POST /schedule_jobs
    # -------------------------

    async def test_create_schedule_job_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            name="Parent Config",
            task_func="tasks.example",
            interval_seconds=60,
        )
        payload = ScheduleJobCreate(
            name="Test Job",
            schedule_config_id=config.id,
            status=ScheduleJobStatus.PENDING,
            started_at=datetime.now(timezone.utc),
        )

        response = await client.post(self.base_url(), json=payload.model_dump(mode="json"))

        assert_status_code(response, 201)
        created = ScheduleJobRead.model_validate(response.json())
        assert_json_contains(response, {"name": "Test Job", "status": ScheduleJobStatus.PENDING})
        assert created.schedule_config_id == config.id

    async def test_create_schedule_job_without_config_success(
        self,
        client: AsyncClient,
    ):
        """schedule_config_id is nullable, so creating a job without it should succeed."""
        payload = ScheduleJobCreate(
            name="Standalone Job",
            status=ScheduleJobStatus.SUCCESS,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )

        response = await client.post(self.base_url(), json=payload.model_dump(mode="json"))

        assert_status_code(response, 201)
        created = ScheduleJobRead.model_validate(response.json())
        assert created.schedule_config_id is None

    # -------------------------
    # GET /schedule_jobs
    # -------------------------

    async def test_get_schedule_jobs(
        self,
        client: AsyncClient,
        make_db_batch,
    ):
        await make_db_batch(ScheduleJobRepository, 4, schedule_config_id=None)

        response = await client.get(self.base_url())

        assert_status_code(response, 200)
        assert_paginated_response(response, min_items=4)

    # -------------------------
    # GET /schedule_jobs/{id}
    # -------------------------

    async def test_get_schedule_job_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        job: ScheduleJob = await make_db(
            ScheduleJobRepository,
            name="Fetch Me",
            status=ScheduleJobStatus.SUCCESS,
        )

        response = await client.get(self.base_url(job.id))

        assert_status_code(response, 200)
        retrieved = ScheduleJobRead.model_validate(response.json())
        assert retrieved.id == job.id
        assert retrieved.name == "Fetch Me"
        assert retrieved.status == ScheduleJobStatus.SUCCESS

    async def test_get_schedule_job_not_found(
        self,
        client: AsyncClient,
    ):
        response = await client.get(self.base_url(uuid.uuid4()))

        assert_status_code(response, 404)

    # -------------------------
    # PATCH /schedule_jobs/{id}
    # -------------------------

    async def test_patch_schedule_job_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        job: ScheduleJob = await make_db(
            ScheduleJobRepository,
            name="Before Patch",
            status=ScheduleJobStatus.PENDING,
        )

        response = await client.patch(
            self.base_url(job.id),
            json={"name": "After Patch", "status": ScheduleJobStatus.SUCCESS},
        )

        assert_status_code(response, 200)
        updated = ScheduleJobRead.model_validate(response.json())
        assert updated.name == "After Patch"
        assert updated.status == ScheduleJobStatus.SUCCESS

    async def test_patch_schedule_job_not_found(
        self,
        client: AsyncClient,
    ):
        response = await client.patch(
            self.base_url(uuid.uuid4()),
            json={"name": "Ghost"},
        )

        assert_status_code(response, 404)

    # -------------------------
    # PUT /schedule_jobs/{id}
    # -------------------------

    async def test_put_schedule_job_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        job: ScheduleJob = await make_db(
            ScheduleJobRepository,
            name="Original Job",
            status=ScheduleJobStatus.PENDING,
        )
        put_payload = ScheduleJobCreate(
            name="Replaced Job",
            status=ScheduleJobStatus.FAILURE,
            started_at=datetime.now(timezone.utc),
            error_message="Something went wrong",
        )

        response = await client.put(
            self.base_url(job.id),
            json=put_payload.model_dump(mode="json"),
        )

        assert_status_code(response, 200)
        updated = ScheduleJobRead.model_validate(response.json())
        assert updated.name == "Replaced Job"
        assert updated.status == ScheduleJobStatus.FAILURE
        assert updated.error_message == "Something went wrong"

    # -------------------------
    # DELETE /schedule_jobs/{id}
    # -------------------------

    async def test_delete_schedule_job_success(
        self,
        client: AsyncClient,
        make_db,
    ):
        job: ScheduleJob = await make_db(
            ScheduleJobRepository,
            name="To Be Deleted",
            status=ScheduleJobStatus.PENDING,
        )

        response = await client.delete(self.base_url(job.id))

        assert_status_code(response, 200)
        response_json = response.json()
        assert "message" in response_json
        assert response_json["identity"] == str(job.id)

        # Verify deletion
        response = await client.get(self.base_url(job.id))
        assert_status_code(response, 404)

    async def test_delete_schedule_job_not_found(
        self,
        client: AsyncClient,
    ):
        response = await client.delete(self.base_url(uuid.uuid4()))

        # API returns 200 with success=false when the resource does not exist
        assert_status_code(response, 200)
        assert response.json()["success"] is False
