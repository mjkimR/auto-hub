from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.features.ai_catalogs.models import AICatalog, AICatalogKind, AICatalogState
from app.features.ai_catalogs.policies.daily_quota import DAILY_LIMIT_REJECTION, DailyQuotaPolicy
from app.features.project_management.projects.services import ProjectError

pytestmark = pytest.mark.unit

T0 = datetime(2026, 9, 15, 12, tzinfo=UTC)
JITTER = timedelta(minutes=10)


def make_catalog(**config) -> AICatalog:
    catalog = MagicMock(spec=AICatalog)
    catalog.id = uuid4()
    catalog.kind = AICatalogKind.JULES
    catalog.enabled = True
    catalog.configured_concurrency = 3
    catalog.refresh_jitter_minutes = 10
    catalog.policy_config = {"daily_task_limit": 3, **config}
    catalog.availability_state = AICatalogState.NORMAL
    catalog.available_at = None
    catalog.availability_source = None
    catalog.availability_note = None
    catalog.availability_updated_at = None
    catalog.revision = 1
    return catalog


def make_policy(admitted: list[datetime]) -> DailyQuotaPolicy:
    repo = MagicMock()
    repo.dispatch_times_since = AsyncMock(return_value=admitted)
    return DailyQuotaPolicy(repo)


async def test_admits_while_the_rolling_window_has_room():
    catalog = make_catalog()
    policy = make_policy([T0 - timedelta(hours=20), T0 - timedelta(hours=1)])

    assert await policy.admit(AsyncMock(), catalog, "session:new", T0) is None

    assert catalog.availability_state == AICatalogState.NORMAL
    assert catalog.revision == 1


async def test_reaching_the_limit_holds_until_the_oldest_task_ages_out_of_the_rolling_window():
    catalog = make_catalog()
    oldest = T0 - timedelta(hours=20)
    policy = make_policy([oldest, T0 - timedelta(hours=10), T0 - timedelta(hours=1)])
    dispatch_key = "session:retried"

    assert await policy.admit(AsyncMock(), catalog, dispatch_key, T0) == DAILY_LIMIT_REJECTION

    # Retried work already in the ledger must not count against itself.
    policy.repo.dispatch_times_since.assert_awaited_once_with(
        policy.repo.dispatch_times_since.await_args.args[0],
        catalog.id,
        T0 - timedelta(days=1),
        exclude_dispatch_key=dispatch_key,
    )
    assert catalog.availability_state == AICatalogState.QUOTA_BLOCKED
    assert catalog.available_at == oldest + timedelta(days=1) + JITTER
    assert catalog.availability_source == "daily-task-limit"


async def test_a_lowered_limit_waits_until_enough_tasks_age_out():
    catalog = make_catalog(daily_task_limit=2)
    admitted = [T0 - timedelta(hours=hours) for hours in (20, 15, 10, 1)]
    policy = make_policy(admitted)

    assert await policy.admit(AsyncMock(), catalog, "session:new", T0) == DAILY_LIMIT_REJECTION

    # Three of the four tasks must age out before one more fits under a limit of two.
    assert catalog.available_at == admitted[2] + timedelta(days=1) + JITTER


async def test_calendar_window_counts_from_local_midnight_and_resets_at_the_next_one():
    catalog = make_catalog(window="calendar", timezone="Asia/Seoul")
    policy = make_policy([T0 - timedelta(hours=1)] * 3)
    # T0 is 21:00 in Seoul, so the local day started at 15:00 UTC the previous day.
    local_midnight = datetime(2026, 9, 14, 15, tzinfo=UTC)

    assert await policy.admit(AsyncMock(), catalog, "session:new", T0) == DAILY_LIMIT_REJECTION

    assert policy.repo.dispatch_times_since.await_args.args[2] == local_midnight
    assert catalog.available_at == local_midnight + timedelta(days=1) + JITTER


async def test_an_expired_hold_resumes_normally_when_the_window_has_room():
    catalog = make_catalog()
    catalog.availability_state = AICatalogState.QUOTA_BLOCKED
    catalog.available_at = T0 - timedelta(minutes=1)
    policy = make_policy([T0 - timedelta(hours=2)])

    assert await policy.admit(AsyncMock(), catalog, "session:new", T0) is None

    assert catalog.availability_state == AICatalogState.NORMAL
    assert catalog.available_at is None


async def test_provider_refusal_outside_the_ledger_waits_a_full_window_and_ignores_older_evidence():
    catalog = make_catalog()
    policy = make_policy([])

    await policy.on_quota_signal(AsyncMock(), catalog, T0, T0)
    assert catalog.availability_state == AICatalogState.QUOTA_BLOCKED
    assert catalog.available_at == T0 + timedelta(days=1) + JITTER

    await policy.on_quota_signal(AsyncMock(), catalog, T0 + timedelta(hours=1), T0 + timedelta(hours=1))
    assert catalog.available_at == T0 + timedelta(days=1) + JITTER


def test_policy_config_is_validated_and_normalized():
    policy = make_policy([])

    assert policy.validate_config({"daily_task_limit": 100}) == {
        "daily_task_limit": 100,
        "window": "rolling",
        "timezone": "UTC",
    }
    for invalid in ({}, {"daily_task_limit": 0}, {"daily_task_limit": 5, "timezone": "Mars/Olympus"}):
        with pytest.raises(ProjectError):
            policy.validate_config(invalid)


async def test_a_catalog_without_a_valid_config_is_not_admitted():
    catalog = make_catalog()
    catalog.policy_config = {}

    with pytest.raises(ProjectError):
        await make_policy([]).admit(AsyncMock(), catalog, "session:new", T0)
