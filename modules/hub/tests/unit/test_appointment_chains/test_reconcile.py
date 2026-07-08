"""Unit tests for the reconcile loop, driven entirely against the in-memory fake.

These are the primary demonstration that the feature works: no database, no
Google, fully deterministic (``today`` is injected). The loop operates on a
payload-derived :class:`ChainConfig` plus a persisted :class:`ChainState`.
"""

from datetime import date, timedelta

import pytest
from app.features.tasks.domains.appointment_chain.calendar.base import KIND_CONFIRMED, KIND_TENTATIVE
from app.features.tasks.domains.appointment_chain.calendar.fake import FakeCalendarClient
from app.features.tasks.domains.appointment_chain.reconcile import (
    TENTATIVE_SUFFIX,
    ReconcileActionType,
    reconcile_chain,
)
from app.features.tasks.domains.appointment_chain.schemas import ChainConfig, ChainState

pytestmark = pytest.mark.unit

ANCHOR = date(2026, 7, 1)
INTERVAL = 28
CHAIN_KEY = "cfg-abc123"


def make_config(**overrides) -> ChainConfig:
    base = ChainConfig(
        summary="이발",
        interval_days=INTERVAL,
        calendar_id="primary",
        auto_confirm=True,
        notify_days_before=None,
        initial_anchor_date=ANCHOR,
    )
    return base.model_copy(update=overrides)


def make_state(**overrides) -> ChainState:
    return ChainState(anchor_date=ANCHOR).model_copy(update=overrides)


async def _run(config, state, cal, today):
    return await reconcile_chain(config, state, cal, chain_key=CHAIN_KEY, today=today)


def _types(actions):
    return [a.type for a in actions]


class TestSeeding:
    async def test_first_tick_creates_tentative_at_anchor_plus_interval(self):
        config, state, cal = make_config(), make_state(), FakeCalendarClient()

        actions = await _run(config, state, cal, today=date(2026, 7, 2))

        assert ReconcileActionType.CREATED_TENTATIVE in _types(actions)
        assert state.tentative_date == ANCHOR + timedelta(days=INTERVAL)
        assert state.tentative_event_id is not None

        events = await cal.list_events(calendar_id="primary")
        assert len(events) == 1
        ev = events[0]
        assert ev.start_date == ANCHOR + timedelta(days=INTERVAL)
        assert ev.kind == KIND_TENTATIVE
        assert ev.summary.endswith(TENTATIVE_SUFFIX)
        assert ev.chain_id == CHAIN_KEY

    async def test_second_tick_is_idempotent_when_nothing_changed(self):
        config, state, cal = make_config(), make_state(), FakeCalendarClient()

        await _run(config, state, cal, today=date(2026, 7, 2))
        first_event_id = state.tentative_event_id
        first_date = state.tentative_date

        actions = await _run(config, state, cal, today=date(2026, 7, 3))

        assert _types(actions) == [ReconcileActionType.WAITING]
        assert state.tentative_event_id == first_event_id
        assert state.tentative_date == first_date
        assert len(await cal.list_events(calendar_id="primary")) == 1


class TestConfirmByMove:
    async def test_user_move_confirms_and_reschedules_next(self):
        """The core behaviour: drag the tentative -> it confirms and the NEXT one shifts."""
        config, state, cal = make_config(), make_state(), FakeCalendarClient()

        await _run(config, state, cal, today=date(2026, 7, 2))
        tentative_id = state.tentative_event_id
        assert tentative_id is not None

        # The user drags the tentative appointment to an earlier date.
        moved_to = date(2026, 7, 15)
        await cal.update_event(calendar_id="primary", event_id=tentative_id, start_date=moved_to)

        actions = await _run(config, state, cal, today=date(2026, 7, 16))

        assert ReconcileActionType.CONFIRMED in _types(actions)
        assert ReconcileActionType.CREATED_TENTATIVE in _types(actions)
        assert state.anchor_date == moved_to
        assert state.tentative_date == moved_to + timedelta(days=INTERVAL)

        events = {e.kind: e for e in await cal.list_events(calendar_id="primary")}
        assert events[KIND_CONFIRMED].start_date == moved_to
        assert events[KIND_CONFIRMED].summary == "이발"  # marker dropped on confirm
        assert events[KIND_TENTATIVE].start_date == moved_to + timedelta(days=INTERVAL)

    async def test_moved_event_is_converted_in_place(self):
        config, state, cal = make_config(), make_state(), FakeCalendarClient()
        await _run(config, state, cal, today=date(2026, 7, 2))
        tentative_id = state.tentative_event_id
        assert tentative_id is not None

        await cal.update_event(calendar_id="primary", event_id=tentative_id, start_date=date(2026, 7, 20))
        await _run(config, state, cal, today=date(2026, 7, 21))

        confirmed = await cal.get_event(calendar_id="primary", event_id=tentative_id)
        assert confirmed is not None
        assert confirmed.kind == KIND_CONFIRMED


class TestAutoConfirm:
    async def test_passed_tentative_is_auto_confirmed_when_enabled(self):
        config, state, cal = make_config(auto_confirm=True), make_state(), FakeCalendarClient()
        await _run(config, state, cal, today=date(2026, 7, 2))
        target = state.tentative_date
        assert target is not None

        actions = await _run(config, state, cal, today=target)

        assert ReconcileActionType.CONFIRMED in _types(actions)
        assert state.anchor_date == target
        assert state.tentative_date == target + timedelta(days=INTERVAL)
        kinds = {e.kind for e in await cal.list_events(calendar_id="primary")}
        assert kinds == {KIND_CONFIRMED, KIND_TENTATIVE}

    async def test_passed_tentative_is_left_alone_when_auto_confirm_off(self):
        config, state, cal = make_config(auto_confirm=False), make_state(), FakeCalendarClient()
        await _run(config, state, cal, today=date(2026, 7, 2))
        target = state.tentative_date
        assert target is not None

        actions = await _run(config, state, cal, today=target + timedelta(days=5))

        assert _types(actions) == [ReconcileActionType.WAITING]
        assert state.anchor_date == ANCHOR  # unchanged


class TestDeletionRecovery:
    async def test_deleted_tentative_is_recreated(self):
        config, state, cal = make_config(), make_state(), FakeCalendarClient()
        await _run(config, state, cal, today=date(2026, 7, 2))
        old_id = state.tentative_event_id
        assert old_id is not None

        await cal.delete_event(calendar_id="primary", event_id=old_id)

        actions = await _run(config, state, cal, today=date(2026, 7, 3))

        assert ReconcileActionType.DELETED_DETECTED in _types(actions)
        assert ReconcileActionType.CREATED_TENTATIVE in _types(actions)
        assert state.tentative_event_id is not None
        assert state.tentative_event_id != old_id
        assert len(await cal.list_events(calendar_id="primary")) == 1


class TestNotifications:
    async def test_notifies_within_window_once(self):
        config, state, cal = make_config(notify_days_before=3), make_state(), FakeCalendarClient()

        await _run(config, state, cal, today=date(2026, 7, 2))
        target = state.tentative_date
        assert target is not None
        assert state.last_notified_date is None

        within = target - timedelta(days=2)
        first = await _run(config, state, cal, today=within)
        assert ReconcileActionType.NOTIFY_DUE in _types(first)
        assert state.last_notified_date == target

        second = await _run(config, state, cal, today=within + timedelta(days=1))
        assert ReconcileActionType.NOTIFY_DUE not in _types(second)

    async def test_no_notification_when_disabled(self):
        config, state, cal = make_config(notify_days_before=None), make_state(), FakeCalendarClient()
        await _run(config, state, cal, today=date(2026, 7, 2))
        target = state.tentative_date
        assert target is not None

        actions = await _run(config, state, cal, today=target - timedelta(days=1))
        assert ReconcileActionType.NOTIFY_DUE not in _types(actions)
