"""Select which calendar backend the reconcile task talks to.

Controlled entirely by environment variables so no code change is needed to go
from local (fake) to production (google):

    CALENDAR_BACKEND=fake     # default — in-memory, no credentials
    CALENDAR_BACKEND=google
    GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/sa-key.json
"""

from __future__ import annotations

from functools import lru_cache

from app.features.tasks.domains.appointment_chain.calendar.base import CalendarPort
from app.features.tasks.domains.appointment_chain.calendar.fake import shared_fake_client
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CalendarSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    CALENDAR_BACKEND: str = Field(default="fake", description="Calendar backend to use: 'fake' or 'google'.")
    GOOGLE_SERVICE_ACCOUNT_FILE: str | None = Field(
        default=None,
        description="Path to the Google service account JSON key, e.g. ~/.config/scheduler-mgr/sa-key.json. "
        "Required when backend is 'google'. Keep it outside the repo. "
        "The target calendar id is not set here -- it is a per-chain task payload field.",
    )


@lru_cache
def get_calendar_settings() -> CalendarSettings:
    return CalendarSettings(**{})


def get_calendar_client(settings: CalendarSettings | None = None) -> CalendarPort:
    """Return the configured calendar client.

    Defaults to the in-memory fake so the app runs with zero setup. When
    ``CALENDAR_BACKEND=google`` the Google adapter is lazily constructed (its
    heavy dependencies are only imported then).
    """
    settings = settings or get_calendar_settings()
    backend = settings.CALENDAR_BACKEND.lower()

    if backend == "google":
        if not settings.GOOGLE_SERVICE_ACCOUNT_FILE:
            raise ValueError(
                "CALENDAR_BACKEND=google requires GOOGLE_SERVICE_ACCOUNT_FILE to point to a service account key."
            )
        from app.features.tasks.domains.appointment_chain.calendar.google import GoogleCalendarClient

        return GoogleCalendarClient(settings.GOOGLE_SERVICE_ACCOUNT_FILE)

    if backend == "fake":
        return shared_fake_client()

    raise ValueError(f"Unknown CALENDAR_BACKEND '{settings.CALENDAR_BACKEND}'. Expected 'fake' or 'google'.")
