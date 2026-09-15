from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.features.ai_catalogs.models import AICatalog, AICatalogState
from app.features.ai_catalogs.schemas import SetAvailabilityRequest
from app.features.ai_catalogs.services import AICatalogService
from app.features.project_management.pipeline_runs.models import PipelineRun

pytestmark = pytest.mark.unit

T0 = datetime(2026, 9, 15, 12, tzinfo=UTC)


def make_catalog(*, short_refresh_enabled: bool = True) -> AICatalog:
    catalog = MagicMock(spec=AICatalog)
    catalog.enabled = True
    catalog.configured_concurrency = 1
    catalog.probe_started_at = None
    catalog.probe_window_minutes = 10
    catalog.short_refresh_enabled = short_refresh_enabled
    catalog.short_refresh_cycle_minutes = 300
    catalog.long_refresh_cycle_minutes = 10_080
    catalog.refresh_jitter_minutes = 10
    catalog.short_refresh_failure_count = 0
    catalog.last_refreshed_at = None
    catalog.usage_window_started_at = None
    catalog.available_at = None
    catalog.availability_state = AICatalogState.NORMAL
    catalog.availability_source = None
    catalog.availability_note = None
    catalog.availability_updated_at = None
    catalog.revision = 1
    return catalog


def make_service(catalog: AICatalog) -> AICatalogService:
    repo = MagicMock()
    repo.get = AsyncMock(return_value=catalog)
    repo.get_by_key = AsyncMock(return_value=catalog)
    repo.active_run_count = AsyncMock(return_value=0)
    return AICatalogService(repo)


def make_run() -> PipelineRun:
    return cast(PipelineRun, SimpleNamespace(ai_catalog_id=object(), quota_block_count=0))


async def deliver_probe_at_hold_end(service: AICatalogService, catalog: AICatalog) -> datetime:
    assert catalog.available_at is not None
    probe_at = catalog.available_at
    await service.request_dispatch(AsyncMock(), uuid4(), uuid4(), probe_at)
    await service.record_dispatch_delivered(AsyncMock(), uuid4(), probe_at)
    return probe_at


async def test_each_hold_re_anchors_on_the_probe_through_short_then_long_cycles():
    catalog = make_catalog()
    service = make_service(catalog)
    run = make_run()
    await service.record_dispatch_delivered(AsyncMock(), uuid4(), T0)

    await service.record_quota_event(AsyncMock(), run, T0 + timedelta(minutes=2))
    assert catalog.available_at == T0 + timedelta(hours=5, minutes=10)
    assert catalog.short_refresh_failure_count == 1
    assert catalog.availability_source == "quota-short-cycle"

    # The old window guaranteed only the first hold; the probe is the first task of the next window.
    probe_at = await deliver_probe_at_hold_end(service, catalog)
    assert catalog.usage_window_started_at == probe_at
    await service.record_quota_event(AsyncMock(), run, probe_at + timedelta(minutes=2))
    assert catalog.available_at == probe_at + timedelta(hours=5, minutes=10)
    assert catalog.short_refresh_failure_count == 2

    probe_at = await deliver_probe_at_hold_end(service, catalog)
    await service.record_quota_event(AsyncMock(), run, probe_at + timedelta(minutes=2))
    assert catalog.available_at == probe_at + timedelta(weeks=1, minutes=10)
    assert catalog.availability_source == "quota-long-cycle"
    assert run.quota_block_count == 3


async def test_disabled_short_cycle_uses_long_cycle_immediately():
    catalog = make_catalog(short_refresh_enabled=False)
    catalog.usage_window_started_at = T0
    service = make_service(catalog)

    await service.record_quota_event(AsyncMock(), make_run(), T0 + timedelta(minutes=2))

    assert catalog.available_at == T0 + timedelta(weeks=1, minutes=10)
    assert catalog.short_refresh_failure_count == 0
    assert catalog.availability_source == "quota-long-cycle"


async def test_first_task_after_an_expired_window_opens_the_next_window():
    catalog = make_catalog()
    service = make_service(catalog)

    await service.record_dispatch_delivered(AsyncMock(), uuid4(), T0)
    await service.record_dispatch_delivered(AsyncMock(), uuid4(), T0 + timedelta(hours=4))
    assert catalog.usage_window_started_at == T0
    await service.record_dispatch_delivered(AsyncMock(), uuid4(), T0 + timedelta(hours=6))
    assert catalog.usage_window_started_at == T0 + timedelta(hours=6)

    await service.record_quota_event(AsyncMock(), make_run(), T0 + timedelta(hours=8))

    assert catalog.available_at == T0 + timedelta(hours=11, minutes=10)


async def test_reply_outside_the_known_window_waits_conservatively_from_the_reply():
    catalog = make_catalog()
    catalog.usage_window_started_at = T0 - timedelta(days=3)
    service = make_service(catalog)

    await service.record_quota_event(AsyncMock(), make_run(), T0)

    assert catalog.available_at == T0 + timedelta(hours=5, minutes=10)
    assert catalog.short_refresh_failure_count == 1


async def test_replies_from_one_exhaustion_consume_a_single_short_retry():
    catalog = make_catalog()
    service = make_service(catalog)
    run = make_run()

    for offset in range(3):
        await service.record_quota_event(AsyncMock(), run, T0 + timedelta(seconds=offset))

    assert catalog.available_at == T0 + timedelta(hours=5, minutes=10)
    assert catalog.short_refresh_failure_count == 1
    assert run.quota_block_count == 3


async def test_late_reply_never_moves_a_verified_hold_earlier():
    catalog = make_catalog()
    catalog.availability_state = AICatalogState.QUOTA_BLOCKED
    catalog.available_at = T0 + timedelta(days=3)
    catalog.availability_source = "local-codex-cli"
    service = make_service(catalog)

    await service.record_quota_event(AsyncMock(), make_run(), T0 - timedelta(minutes=1))

    assert catalog.available_at == T0 + timedelta(days=3)
    assert catalog.availability_source == "local-codex-cli"
    assert catalog.short_refresh_failure_count == 0


async def test_probe_window_starts_only_after_the_probe_is_delivered():
    catalog = make_catalog()
    catalog.availability_state = AICatalogState.QUOTA_BLOCKED
    catalog.available_at = T0 - timedelta(minutes=1)
    catalog.usage_window_started_at = T0 - timedelta(hours=5)
    catalog.short_refresh_failure_count = 2
    service = make_service(catalog)
    session = AsyncMock()
    catalog_id, run_id = uuid4(), uuid4()

    await service.request_dispatch(session, catalog_id, run_id, T0)
    assert catalog.availability_state == AICatalogState.PROBE
    assert catalog.probe_started_at is None
    assert catalog.usage_window_started_at is None
    assert catalog.last_refreshed_at == T0 - timedelta(minutes=1)

    # An admitted probe that never posted must not restore normal concurrency.
    await service.request_dispatch(session, catalog_id, run_id, T0 + timedelta(minutes=30))
    assert catalog.availability_state == AICatalogState.PROBE

    await service.record_dispatch_delivered(session, catalog_id, T0 + timedelta(minutes=31))
    assert catalog.probe_started_at == T0 + timedelta(minutes=31)
    assert catalog.usage_window_started_at == T0 + timedelta(minutes=31)
    await service.request_dispatch(session, catalog_id, run_id, T0 + timedelta(minutes=41))
    assert catalog.availability_state == AICatalogState.NORMAL
    assert catalog.short_refresh_failure_count == 0


async def test_disabled_catalog_keeps_its_hold_through_re_enabling():
    catalog = make_catalog()
    service = make_service(catalog)
    session = AsyncMock()
    hold = datetime.now(UTC) + timedelta(days=1)

    await service.set_enabled(session, "personal-codex", False, datetime.now(UTC))
    await service.set_availability(
        session, "personal-codex", SetAvailabilityRequest(available_at=hold), datetime.now(UTC)
    )
    assert catalog.availability_state == AICatalogState.DISABLED
    assert catalog.available_at == hold

    await service.set_enabled(session, "personal-codex", True, datetime.now(UTC))
    assert catalog.availability_state == AICatalogState.QUOTA_BLOCKED
    assert catalog.available_at == hold
