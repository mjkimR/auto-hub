from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.features.ai_catalogs.models import AICatalog, AICatalogState
from app.features.ai_catalogs.services import AICatalogService
from app.features.project_management.pipeline_runs.models import PipelineRun

pytestmark = pytest.mark.unit


def make_catalog(*, short_refresh_enabled: bool = True) -> AICatalog:
    catalog = MagicMock(spec=AICatalog)
    catalog.short_refresh_enabled = short_refresh_enabled
    catalog.short_refresh_cycle_minutes = 300
    catalog.long_refresh_cycle_minutes = 10_080
    catalog.refresh_jitter_minutes = 10
    catalog.short_refresh_failure_count = 0
    catalog.last_refreshed_at = None
    catalog.available_at = None
    catalog.availability_state = AICatalogState.NORMAL
    catalog.availability_source = None
    catalog.availability_note = None
    catalog.availability_updated_at = None
    catalog.revision = 1
    return catalog


async def test_quota_blocks_follow_refresh_anchor_through_short_then_long_cycles():
    catalog = make_catalog()
    repo = MagicMock()
    repo.get = AsyncMock(return_value=catalog)
    service = AICatalogService(repo)
    session = AsyncMock()
    run = cast(PipelineRun, SimpleNamespace(ai_catalog_id=object(), quota_block_count=0))
    anchor = datetime.now(UTC) + timedelta(minutes=1)
    catalog.last_refreshed_at = anchor

    await service.record_quota_event(session, run, anchor + timedelta(minutes=2))
    assert catalog.available_at == anchor + timedelta(hours=5, minutes=10)
    assert catalog.short_refresh_failure_count == 1
    assert catalog.availability_source == "quota-short-cycle"

    assert catalog.available_at is not None
    second_anchor = catalog.available_at
    catalog.last_refreshed_at = second_anchor
    await service.record_quota_event(session, run, second_anchor + timedelta(minutes=2))
    assert catalog.available_at == anchor + timedelta(hours=10, minutes=20)
    assert catalog.short_refresh_failure_count == 2

    assert catalog.available_at is not None
    third_anchor = catalog.available_at
    catalog.last_refreshed_at = third_anchor
    await service.record_quota_event(session, run, third_anchor + timedelta(minutes=2))
    assert catalog.available_at == anchor + timedelta(hours=10, minutes=30, weeks=1)
    assert catalog.availability_source == "quota-long-cycle"
    assert run.quota_block_count == 3


async def test_disabled_short_cycle_uses_long_cycle_immediately():
    catalog = make_catalog(short_refresh_enabled=False)
    repo = MagicMock()
    repo.get = AsyncMock(return_value=catalog)
    service = AICatalogService(repo)
    session = AsyncMock()
    run = cast(PipelineRun, SimpleNamespace(ai_catalog_id=object(), quota_block_count=0))
    anchor = datetime.now(UTC) + timedelta(minutes=1)
    catalog.last_refreshed_at = anchor

    await service.record_quota_event(session, run, anchor + timedelta(minutes=2))

    assert catalog.available_at == anchor + timedelta(weeks=1, minutes=10)
    assert catalog.short_refresh_failure_count == 0
    assert catalog.availability_source == "quota-long-cycle"
