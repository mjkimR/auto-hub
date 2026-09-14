"""Integration tests for the generic task_states store (load / upsert round trip)."""

from uuid import UUID, uuid4

import pytest
from app.features.execution.task_states import store as task_state_store

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

    async def test_all_digit_uuid_round_trips(self, session):
        """A uuid whose hex is all decimal digits must survive SQLite's NUMERIC affinity.

        With a ``sa.UUID`` column SQLite coerces such a key to a float, and reading the
        row back raises. Pins the ``sa.Uuid`` (CHAR(32)) column type.
        """
        config_id = UUID("11111111-1111-1111-1111-111111111111")
        await task_state_store.upsert(session, config_id, {"count": 1})
        await session.commit()

        assert await task_state_store.load(session, config_id) == {"count": 1}
