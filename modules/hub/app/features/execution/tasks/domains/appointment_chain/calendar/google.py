"""Google Calendar backend (Service Account auth).

STATUS: scaffolded but not yet exercised. It is intentionally decoupled so the
rest of the feature works today against the fake backend. To activate it later:

1. Install the client libs (kept out of the default deps on purpose)::

       uv add --package scheduler-mgr google-api-python-client google-auth

2. Create a GCP project, enable the Google Calendar API, create a **Service
   Account**, and download its JSON key. Grant that service account **no project
   IAM roles** -- calendar access comes from the calendar's ACL, not from IAM, so
   any role here only widens the blast radius if the key leaks. Never enable
   domain-wide delegation.

3. Create a **dedicated** calendar for these chains (never share your primary
   calendar: the service account would see every personal event, and a bug here
   could delete them). **Share** it with the service account's email
   (``...@...iam.gserviceaccount.com``) granting "Make changes to events" --
   not "Make changes AND manage sharing".

4. Point the app at the key and flip the backend::

       CALENDAR_BACKEND=google
       GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/sa-key.json

5. Set each chain's ``calendar_id`` payload field to that calendar's real id
   (Settings -> Integrate calendar -> Calendar ID, e.g.
   ``...@group.calendar.google.com``). Under service-account auth ``"primary"``
   resolves to the service account's *own* empty calendar, not yours.

Google's ``googleapiclient`` is synchronous, so every call is offloaded to a
thread via :func:`asyncio.to_thread` to keep the async CalendarPort contract.
All-day events are represented with ``start.date`` / ``end.date`` (end is the
day after start, per the Calendar API's half-open convention).
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

from app.features.execution.tasks.domains.appointment_chain.calendar.base import CalendarEvent

# Least privilege: events-only. Deliberately *not* ".../auth/calendar", which would
# also permit deleting calendars and rewriting their sharing ACLs.
_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


@lru_cache(maxsize=1)
def _build_service(service_account_file: str) -> Any:
    """Build (and cache) the Calendar v3 service client. Lazy-imports google libs."""
    from google.oauth2 import service_account  # type: ignore[import-not-found]
    from googleapiclient.discovery import build  # type: ignore[import-not-found]

    credentials = service_account.Credentials.from_service_account_file(service_account_file, scopes=_SCOPES)
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _to_event(calendar_id: str, raw: dict[str, Any]) -> CalendarEvent:
    start = raw.get("start", {})
    # All-day events use "date"; fall back to the date part of a timed "dateTime".
    raw_date = start.get("date") or (start.get("dateTime", "")[:10])
    private = (raw.get("extendedProperties", {}) or {}).get("private", {}) or {}
    return CalendarEvent(
        id=raw["id"],
        calendar_id=calendar_id,
        summary=raw.get("summary", ""),
        start_date=date.fromisoformat(raw_date),
        extended_private={str(k): str(v) for k, v in private.items()},
    )


def _all_day_body(summary: str, start_date: date, extended_private: dict[str, str]) -> dict[str, Any]:
    return {
        "summary": summary,
        "start": {"date": start_date.isoformat()},
        "end": {"date": (start_date + timedelta(days=1)).isoformat()},
        "extendedProperties": {"private": dict(extended_private)},
    }


class GoogleCalendarClient:
    """CalendarPort implementation backed by the Google Calendar API."""

    def __init__(self, service_account_file: str) -> None:
        self._service_account_file = service_account_file

    @property
    def _service(self) -> Any:
        return _build_service(self._service_account_file)

    async def create_event(
        self,
        *,
        calendar_id: str,
        summary: str,
        start_date: date,
        extended_private: dict[str, str],
    ) -> CalendarEvent:
        body = _all_day_body(summary, start_date, extended_private)
        raw = await asyncio.to_thread(
            lambda: self._service.events().insert(calendarId=calendar_id, body=body).execute()
        )
        return _to_event(calendar_id, raw)

    async def get_event(self, *, calendar_id: str, event_id: str) -> CalendarEvent | None:
        from googleapiclient.errors import HttpError  # type: ignore[import-not-found]

        try:
            raw = await asyncio.to_thread(
                lambda: self._service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            )
        except HttpError as exc:  # 404 or 410 (deleted) => treat as gone
            if exc.resp.status in (404, 410):
                return None
            raise
        if raw.get("status") == "cancelled":
            return None
        return _to_event(calendar_id, raw)

    async def update_event(
        self,
        *,
        calendar_id: str,
        event_id: str,
        summary: str | None = None,
        start_date: date | None = None,
        extended_private: dict[str, str] | None = None,
    ) -> CalendarEvent:
        patch: dict[str, Any] = {}
        if summary is not None:
            patch["summary"] = summary
        if start_date is not None:
            patch["start"] = {"date": start_date.isoformat()}
            patch["end"] = {"date": (start_date + timedelta(days=1)).isoformat()}
        if extended_private is not None:
            patch["extendedProperties"] = {"private": dict(extended_private)}
        raw = await asyncio.to_thread(
            lambda: self._service.events().patch(calendarId=calendar_id, eventId=event_id, body=patch).execute()
        )
        return _to_event(calendar_id, raw)

    async def delete_event(self, *, calendar_id: str, event_id: str) -> None:
        from googleapiclient.errors import HttpError  # type: ignore[import-not-found]

        try:
            await asyncio.to_thread(
                lambda: self._service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            )
        except HttpError as exc:
            if exc.resp.status not in (404, 410):
                raise

    async def list_events(self, *, calendar_id: str, chain_id: str | None = None) -> list[CalendarEvent]:
        kwargs: dict[str, Any] = {
            "calendarId": calendar_id,
            "singleEvents": True,
            "orderBy": "startTime",
            "showDeleted": False,
        }
        if chain_id is not None:
            kwargs["privateExtendedProperty"] = f"chain_id={chain_id}"
        raw = await asyncio.to_thread(lambda: self._service.events().list(**kwargs).execute())
        return [_to_event(calendar_id, item) for item in raw.get("items", [])]
