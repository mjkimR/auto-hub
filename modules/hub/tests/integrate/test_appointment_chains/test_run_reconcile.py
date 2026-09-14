"""Integration test: run_reconcile end-to-end through the real DB-backed state store.

Proves the whole lean path: config comes in as a payload, evolving state is loaded
from and persisted to the generic ``task_states`` table across ticks, and the
core "user moves the appointment -> next one reschedules" cycle survives a round
trip through the database.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from app.features.execution.task_states import store as task_state_store
from app.features.execution.tasks.domains.appointment_chain import run_reconcile
from app.features.execution.tasks.domains.appointment_chain.calendar.base import KIND_CONFIRMED, KIND_TENTATIVE
from app.features.execution.tasks.domains.appointment_chain.calendar.fake import reset_shared_store, shared_fake_client
from app.features.execution.tasks.domains.appointment_chain.schemas import ChainConfig, ChainState
from app_layer_base.core.database.transaction import AsyncTransaction

pytestmark = pytest.mark.integrate


def make_config(**overrides) -> ChainConfig:
    base = ChainConfig(summary="이발", interval_days=28, initial_anchor_date=date(2026, 7, 1))
    return base.model_copy(update=overrides)


async def _load_state(config_id) -> ChainState:
    async with AsyncTransaction() as session:
        raw = await task_state_store.load(session, config_id)
    assert raw is not None
    return ChainState(**raw)


@pytest.mark.real_commit
class TestRunReconcile:
    @pytest.fixture(autouse=True)
    def _isolate_calendar(self):
        reset_shared_store()
        yield
        reset_shared_store()

    async def test_first_tick_seeds_and_persists_state(self, session):
        config_id = uuid4()

        await run_reconcile(make_config(), config_id=config_id, today=date(2026, 7, 2))

        state = await _load_state(config_id)
        assert state.tentative_event_id is not None
        assert state.tentative_date == date(2026, 7, 29)

        events = await shared_fake_client().list_events(calendar_id="primary")
        assert len(events) == 1
        assert events[0].kind == KIND_TENTATIVE

    async def test_state_survives_round_trip_and_reschedules_after_move(self, session):
        config = make_config()
        config_id = uuid4()

        # Tick 1: seed (state written to task_states).
        await run_reconcile(config, config_id=config_id, today=date(2026, 7, 2))
        tentative_id = (await _load_state(config_id)).tentative_event_id
        assert tentative_id is not None

        # The user drags the appointment.
        moved_to = date(2026, 7, 15)
        await shared_fake_client().update_event(calendar_id="primary", event_id=tentative_id, start_date=moved_to)

        # Tick 2: a *fresh* run loads the persisted state and reconciles the move.
        await run_reconcile(config, config_id=config_id, today=date(2026, 7, 16))

        state = await _load_state(config_id)
        assert state.anchor_date == moved_to
        assert state.tentative_date == moved_to + timedelta(days=28)

        events = {e.kind: e for e in await shared_fake_client().list_events(calendar_id="primary")}
        assert events[KIND_CONFIRMED].start_date == moved_to
        assert events[KIND_TENTATIVE].start_date == moved_to + timedelta(days=28)

    async def test_separate_configs_keep_independent_state(self, session):
        config = make_config()
        id_a, id_b = uuid4(), uuid4()

        await run_reconcile(config, config_id=id_a, today=date(2026, 7, 2))

        async with AsyncTransaction() as s:
            assert await task_state_store.load(s, id_a) is not None
            assert await task_state_store.load(s, id_b) is None
