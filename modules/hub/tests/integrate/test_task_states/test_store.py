"""Integration tests for the generic task_states store (load / upsert round trip)."""

from uuid import uuid4

import pytest
from app.features.task_states import store as task_state_store

pytestmark = pytest.mark.integrate


@pytest.mark.real_commit
class TestTaskStateStore:
    async def test_load_missing_returns_none(self, session):
        assert await task_state_store.load(session, uuid4()) is None

    async def test_upsert_then_load_round_trips(self, session):
        config_id = uuid4()
        await task_state_store.upsert(session, config_id, {"anchor_date": "2026-07-01", "count": 1})
        await session.commit()

        loaded = await task_state_store.load(session, config_id)
        assert loaded == {"anchor_date": "2026-07-01", "count": 1}

    async def test_upsert_replaces_existing(self, session):
        config_id = uuid4()
        await task_state_store.upsert(session, config_id, {"count": 1})
        await session.commit()
        await task_state_store.upsert(session, config_id, {"count": 2, "extra": "x"})
        await session.commit()

        loaded = await task_state_store.load(session, config_id)
        assert loaded == {"count": 2, "extra": "x"}
