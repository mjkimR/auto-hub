"""Calendar port: the boundary between the reconcile logic and any concrete calendar.

The reconcile loop never talks to Google directly. It depends only on
:class:`CalendarPort`, so the exact same logic runs against:

- :class:`~app.features.tasks.domains.appointment_chain.calendar.fake.FakeCalendarClient` (in-memory)
  for local development and tests — no Google account, no credentials, no card.
- ``GoogleCalendarClient`` (see :mod:`.google`) once a Service Account is wired up.

Appointments are modelled as **all-day events keyed by a single date**, which matches
the "예약일자" semantics of a recurring appointment far better than timed events.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

# Keys used inside a calendar event's ``extendedProperties.private`` bag so that
# our events are self-identifying when the calendar is polled.
EXT_CHAIN_ID = "chain_id"
EXT_KIND = "kind"

KIND_TENTATIVE = "tentative"
KIND_CONFIRMED = "confirmed"


class CalendarEvent(BaseModel):
    """Normalized, backend-agnostic view of a single all-day calendar event."""

    id: str = Field(description="Backend-assigned event id.")
    calendar_id: str = Field(description="Id of the calendar the event lives on (e.g. 'primary').")
    summary: str = Field(description="Event title as shown in the calendar UI.")
    start_date: date = Field(description="The (all-day) date of the appointment.")
    extended_private: dict[str, str] = Field(
        default_factory=dict,
        description="Private key/value metadata we stash on the event (chain_id, kind, ...).",
    )

    @property
    def chain_id(self) -> str | None:
        return self.extended_private.get(EXT_CHAIN_ID)

    @property
    def kind(self) -> str | None:
        return self.extended_private.get(EXT_KIND)


@runtime_checkable
class CalendarPort(Protocol):
    """Minimal async calendar interface the reconcile loop depends on.

    All methods are keyword-only to keep call sites self-documenting. Concrete
    implementations do not need to inherit from this Protocol; structural typing
    is enough.
    """

    async def create_event(
        self,
        *,
        calendar_id: str,
        summary: str,
        start_date: date,
        extended_private: dict[str, str],
    ) -> CalendarEvent: ...

    async def get_event(self, *, calendar_id: str, event_id: str) -> CalendarEvent | None: ...

    async def update_event(
        self,
        *,
        calendar_id: str,
        event_id: str,
        summary: str | None = None,
        start_date: date | None = None,
        extended_private: dict[str, str] | None = None,
    ) -> CalendarEvent: ...

    async def delete_event(self, *, calendar_id: str, event_id: str) -> None: ...

    async def list_events(self, *, calendar_id: str, chain_id: str | None = None) -> list[CalendarEvent]: ...
