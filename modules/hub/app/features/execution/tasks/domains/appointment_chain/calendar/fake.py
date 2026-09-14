"""In-memory calendar backend for local development and tests.

Two ways to use it:

- **Tests**: construct ``FakeCalendarClient()`` with its own private store, so each
  test is isolated. Simulate a user dragging an event by calling
  :meth:`update_event` with a new ``start_date``.
- **Local dogfooding**: :func:`get_calendar_client` hands out clients bound to a
  process-global store (:data:`_SHARED_STORE`) so events survive across dispatcher
  ticks while the server is running.
"""

from __future__ import annotations

import uuid
from datetime import date

from app.features.execution.tasks.domains.appointment_chain.calendar.base import CalendarEvent

# calendar_id -> {event_id -> CalendarEvent}
Store = dict[str, dict[str, CalendarEvent]]

# Process-global store used by the real task via the factory (see factory.py).
_SHARED_STORE: Store = {}


class FakeCalendarClient:
    """A :class:`~app.features.execution.tasks.domains.appointment_chain.calendar.base.CalendarPort`
    implementation backed by a plain dict."""

    def __init__(self, store: Store | None = None) -> None:
        # Default to a fresh, private store (test-friendly). Pass the shared store
        # explicitly for cross-tick persistence.
        self._store: Store = store if store is not None else {}

    def _calendar(self, calendar_id: str) -> dict[str, CalendarEvent]:
        return self._store.setdefault(calendar_id, {})

    async def create_event(
        self,
        *,
        calendar_id: str,
        summary: str,
        start_date: date,
        extended_private: dict[str, str],
    ) -> CalendarEvent:
        event = CalendarEvent(
            id=f"fake-{uuid.uuid4().hex}",
            calendar_id=calendar_id,
            summary=summary,
            start_date=start_date,
            extended_private=dict(extended_private),
        )
        self._calendar(calendar_id)[event.id] = event
        return event

    async def get_event(self, *, calendar_id: str, event_id: str) -> CalendarEvent | None:
        return self._calendar(calendar_id).get(event_id)

    async def update_event(
        self,
        *,
        calendar_id: str,
        event_id: str,
        summary: str | None = None,
        start_date: date | None = None,
        extended_private: dict[str, str] | None = None,
    ) -> CalendarEvent:
        events = self._calendar(calendar_id)
        current = events.get(event_id)
        if current is None:
            raise KeyError(f"Event '{event_id}' not found on calendar '{calendar_id}'.")
        updated = current.model_copy(
            update={
                k: v
                for k, v in (
                    ("summary", summary),
                    ("start_date", start_date),
                    ("extended_private", dict(extended_private) if extended_private is not None else None),
                )
                if v is not None
            }
        )
        events[event_id] = updated
        return updated

    async def delete_event(self, *, calendar_id: str, event_id: str) -> None:
        self._calendar(calendar_id).pop(event_id, None)

    async def list_events(self, *, calendar_id: str, chain_id: str | None = None) -> list[CalendarEvent]:
        events = list(self._calendar(calendar_id).values())
        if chain_id is not None:
            events = [e for e in events if e.chain_id == chain_id]
        return sorted(events, key=lambda e: e.start_date)


def shared_fake_client() -> FakeCalendarClient:
    """Return a client bound to the process-global store (used for local dogfooding)."""
    return FakeCalendarClient(store=_SHARED_STORE)


def reset_shared_store() -> None:
    """Clear the process-global store. Handy from a REPL or a reset endpoint."""
    _SHARED_STORE.clear()
