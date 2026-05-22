"""E2E tests for the Dispatcher API.

Tests the POST /api/v1/dispatchers/trigger endpoint covering:
- Happy path: due schedules are dispatched and ScheduleJobs are created
- Retry jobs: failed jobs with retry_need=True are re-dispatched
- No-op: no due schedules returns dispatched=0
- Disabled / future / expired configs are skipped
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from app.features.schedule_configs.models import ScheduleConfig
from app.features.schedule_configs.repos import ScheduleConfigRepository
from app.features.schedule_jobs.models import ScheduleJob, ScheduleJobStatus
from app.features.schedule_jobs.repos import ScheduleJobRepository
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils.assertions import assert_json_contains, assert_status_code

BASE_URL = "/api/v1/dispatchers/trigger"


async def _noop(**kwargs):
    """Dummy task that completes successfully."""
    pass


async def _failing(**kwargs):
    """Dummy task that always raises."""
    raise RuntimeError("task failed")


@pytest.mark.e2e
@pytest.mark.real_commit
class TestDispatcherTriggerAPI:
    """E2E tests for POST /api/v1/dispatchers/trigger."""

    # ------------------------------------------------------------------
    # Happy path – due configs are dispatched
    # ------------------------------------------------------------------
    async def test_trigger_dispatches_due_config(
        self,
        client: AsyncClient,
        make_db,
        session: AsyncSession,
    ):
        """A single due config should result in dispatched=1 and a ScheduleJob record."""
        past = datetime.now(UTC) - timedelta(minutes=5)
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            _use_default=True,
            name="due-config",
            interval_seconds=60,
            next_run_at=past,
            last_run_at=past - timedelta(minutes=5),
        )

        with patch("app.features.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _noop
            response = await client.post(BASE_URL)

        assert_status_code(response, 200)
        assert_json_contains(response, {"dispatched": 1})

        # Verify ScheduleJob was created in the DB
        from sqlalchemy import select

        result = await session.execute(select(ScheduleJob).where(ScheduleJob.schedule_config_id == config.id))
        jobs = result.scalars().all()
        assert len(jobs) >= 1

    async def test_trigger_no_due_configs_returns_zero(
        self,
        client: AsyncClient,
    ):
        """When there are no due configs, dispatched should be 0."""
        with patch("app.features.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _noop
            response = await client.post(BASE_URL)

        assert_status_code(response, 200)
        assert response.json()["dispatched"] == 0

    async def test_trigger_dispatches_multiple_due_configs(
        self,
        client: AsyncClient,
        make_db_batch,
    ):
        """Multiple due configs should all be dispatched."""
        past = datetime.now(UTC) - timedelta(minutes=1)
        await make_db_batch(
            ScheduleConfigRepository,
            3,
            _use_default=True,
            interval_seconds=60,
            next_run_at=past,
        )

        with patch("app.features.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _noop
            response = await client.post(BASE_URL)

        assert_status_code(response, 200)
        assert response.json()["dispatched"] >= 3

    # ------------------------------------------------------------------
    # Config filtering – disabled / future / expired are skipped
    # ------------------------------------------------------------------

    async def test_trigger_skips_disabled_config(
        self,
        client: AsyncClient,
        make_db,
    ):
        """Disabled configs must not be dispatched."""
        past = datetime.now(UTC) - timedelta(minutes=5)
        await make_db(
            ScheduleConfigRepository,
            _use_default=True,
            name="disabled-config",
            interval_seconds=60,
            enabled=False,
            next_run_at=past,
        )

        with patch("app.features.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _noop
            response = await client.post(BASE_URL)

        assert_status_code(response, 200)
        assert response.json()["dispatched"] == 0

    async def test_trigger_skips_future_next_run_at(
        self,
        client: AsyncClient,
        make_db,
    ):
        """Configs whose next_run_at is in the future must not be dispatched."""
        future = datetime.now(UTC) + timedelta(hours=1)
        await make_db(
            ScheduleConfigRepository,
            _use_default=True,
            name="future-config",
            interval_seconds=60,
            next_run_at=future,
        )

        with patch("app.features.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _noop
            response = await client.post(BASE_URL)

        assert_status_code(response, 200)
        assert response.json()["dispatched"] == 0

    async def test_trigger_skips_expired_config(
        self,
        client: AsyncClient,
        make_db,
    ):
        """Configs whose end_at has already passed must not be dispatched."""
        now = datetime.now(UTC)
        await make_db(
            ScheduleConfigRepository,
            _use_default=True,
            name="expired-config",
            interval_seconds=60,
            end_at=now - timedelta(seconds=1),
            next_run_at=now - timedelta(minutes=1),
        )

        with patch("app.features.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _noop
            response = await client.post(BASE_URL)

        assert_status_code(response, 200)
        assert response.json()["dispatched"] == 0

    async def test_trigger_skips_config_before_start_at(
        self,
        client: AsyncClient,
        make_db,
    ):
        """Configs whose start_at has not been reached must not be dispatched."""
        now = datetime.now(UTC)
        await make_db(
            ScheduleConfigRepository,
            _use_default=True,
            name="not-started-config",
            interval_seconds=60,
            start_at=now + timedelta(hours=1),
            next_run_at=now - timedelta(minutes=1),
        )

        with patch("app.features.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _noop
            response = await client.post(BASE_URL)

        assert_status_code(response, 200)
        assert response.json()["dispatched"] == 0

    # ------------------------------------------------------------------
    # next_run_at update after dispatch
    # ------------------------------------------------------------------

    async def test_trigger_updates_next_run_at_after_dispatch(
        self,
        client: AsyncClient,
        make_db,
        session: AsyncSession,
    ):
        """After dispatch, next_run_at on the config should be updated to a future time."""
        past = datetime.now(UTC) - timedelta(minutes=5)
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            _use_default=True,
            name="interval-config",
            interval_seconds=60,
            next_run_at=past,
            last_run_at=past - timedelta(minutes=5),
        )

        with patch("app.features.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _noop
            response = await client.post(BASE_URL)

        assert_status_code(response, 200)

        await session.refresh(config)
        assert config.next_run_at is not None
        # Normalize to UTC-aware before comparing.
        next_run_at = config.next_run_at
        if next_run_at.tzinfo is None:
            next_run_at = next_run_at.replace(tzinfo=UTC)
        assert next_run_at > datetime.now(UTC)

    # ------------------------------------------------------------------
    # Retry jobs
    # ------------------------------------------------------------------

    async def test_trigger_retries_failed_job(
        self,
        client: AsyncClient,
        make_db,
        session: AsyncSession,
    ):
        """A failed job with retry_need=True should be retried on the next trigger."""
        # Create a config that is NOT due (future next_run_at) so only the retry path runs
        future = datetime.now(UTC) + timedelta(hours=1)
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            _use_default=True,
            name="retry-config",
            interval_seconds=60,
            next_run_at=future,
            last_run_at=None,
        )
        # Create a failed job that needs retry
        job: ScheduleJob = await make_db(
            ScheduleJobRepository,
            name=config.name,
            schedule_config_id=config.id,
            status=ScheduleJobStatus.FAILURE,
            retry_need=True,
            retry_attempts=0,
            retry_max=3,
            started_at=datetime.now(UTC) - timedelta(minutes=10),
        )

        with patch("app.features.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _noop
            response = await client.post(BASE_URL)

        assert_status_code(response, 200)

        await session.refresh(job)
        assert job.status == ScheduleJobStatus.SUCCESS

    async def test_trigger_does_not_retry_when_max_attempts_reached(
        self,
        client: AsyncClient,
        make_db,
        session: AsyncSession,
    ):
        """A failed job that has exhausted retry_max should NOT be retried."""
        future = datetime.now(UTC) + timedelta(hours=1)
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            _use_default=True,
            name="no-retry-config",
            interval_seconds=60,
            next_run_at=future,
            last_run_at=None,
        )
        job: ScheduleJob = await make_db(
            ScheduleJobRepository,
            name=config.name,
            schedule_config_id=config.id,
            status=ScheduleJobStatus.FAILURE,
            retry_need=True,
            retry_attempts=3,
            retry_max=3,
            started_at=datetime.now(UTC) - timedelta(minutes=10),
        )

        with patch("app.features.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _noop
            response = await client.post(BASE_URL)

        assert_status_code(response, 200)

        await session.refresh(job)
        # Status must remain FAILURE – no retry was attempted
        assert job.status == ScheduleJobStatus.FAILURE

    # ------------------------------------------------------------------
    # Task failure reflected in ScheduleJob
    # ------------------------------------------------------------------

    async def test_trigger_records_failure_when_task_raises(
        self,
        client: AsyncClient,
        make_db,
        session: AsyncSession,
    ):
        """When the dispatched task raises an exception, the ScheduleJob should be FAILURE."""
        past = datetime.now(UTC) - timedelta(minutes=5)
        config: ScheduleConfig = await make_db(
            ScheduleConfigRepository,
            _use_default=True,
            name="failing-task-config",
            interval_seconds=60,
            next_run_at=past,
            last_run_at=None,
        )

        with patch("app.features.dispatchers.services.task_registry") as mock_registry:
            mock_registry.get.return_value = _failing
            response = await client.post(BASE_URL)

        assert_status_code(response, 200)

        from sqlalchemy import select

        result = await session.execute(select(ScheduleJob).where(ScheduleJob.schedule_config_id == config.id))
        jobs = result.scalars().all()
        assert len(jobs) >= 1
        assert all(j.status == ScheduleJobStatus.FAILURE for j in jobs)
        assert all(j.error_message is not None for j in jobs)
