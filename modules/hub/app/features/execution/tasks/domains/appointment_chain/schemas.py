"""Config and state schemas for a single appointment chain.

``ChainConfig`` is the **task payload** — the wide, user-owned settings block that
lives in ``ScheduleConfig.payload``. One ScheduleConfig (with
``task_func="calendar.reconcile_chain"``) manages one chain, so its payload
validates against this model. Its JSON schema is exposed via ``/tasks/specs`` and
drives the RJSF payload form in the UI.

``ChainState`` is the **persisted state** — the evolving cursor the reconcile loop
keeps between ticks in the generic ``task_states`` store. Users never touch it.
"""

from datetime import date

from pydantic import BaseModel, Field


class ChainConfig(BaseModel):
    """Task payload: static, user-owned configuration for one appointment chain."""

    summary: str = Field(description="Event title used for the appointment (e.g. '이발').")
    interval_days: int = Field(description="Days between a confirmed appointment and the next one (e.g. 28).", gt=0)
    calendar_id: str = Field(
        default="primary",
        description="Target calendar id. Under the Google backend this must be the calendar's real id "
        "(e.g. '...@group.calendar.google.com'); 'primary' there resolves to the service account's own calendar.",
    )
    auto_confirm: bool = Field(
        default=True, description="Auto-confirm a tentative appointment whose date has passed untouched."
    )
    notify_days_before: int | None = Field(
        default=None, description="Notify this many days before the tentative date. NULL disables it.", ge=0
    )
    initial_anchor_date: date = Field(
        description="Date of the most recent appointment. Seeds the chain on the first run; "
        "afterwards the live anchor is tracked in state and this value is ignored."
    )


class ChainState(BaseModel):
    """Persisted, reconcile-owned state for one appointment chain."""

    anchor_date: date = Field(description="Date of the most recent confirmed appointment; base for the next one.")
    tentative_event_id: str | None = Field(
        default=None, description="Calendar event id of the current tentative appointment, if any."
    )
    tentative_date: date | None = Field(
        default=None, description="Date we last placed the tentative appointment at; used to detect user moves."
    )
    last_notified_date: date | None = Field(
        default=None, description="Tentative date we last notified for; prevents duplicate notifications."
    )
