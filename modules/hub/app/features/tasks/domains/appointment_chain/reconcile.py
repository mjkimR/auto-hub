"""The reconcile loop — the heart of the feature.

A convergence loop (Kubernetes-controller style), not a one-shot sync. Given a
chain's config, its current state, and whatever is on the calendar right now, it
drives the calendar toward the desired state and updates the state in place.

Desired state, in one sentence:

    Exactly one *tentative* appointment should sit ``interval_days`` after the
    most recent confirmed appointment (``state.anchor_date``).

Transitions handled each tick:

- **Seed / recreate**: no tentative event tracked → create one at
  ``anchor_date + interval_days``.
- **Confirm by move**: the tracked tentative event's date differs from where we
  put it → the user dragged it. Treat the new date as confirmed: advance the
  anchor and drop the tentative pointer (a fresh tentative is created in the same
  tick).
- **Auto-confirm**: the tentative date arrived/passed untouched and
  ``auto_confirm`` is on → confirm at that date and roll forward.
- **Notify**: within ``notify_days_before`` of the tentative date, emit a
  notification action (deduped via ``last_notified_date``).

Pure with respect to time and storage: ``today`` is injected and it touches only
``config`` (read), ``state`` (mutated in place), and the ``calendar`` port —
never the database. Returns the actions it took (for logging / assertions).
"""

from datetime import date, timedelta
from enum import StrEnum

from app.features.tasks.domains.appointment_chain.calendar.base import (
    EXT_CHAIN_ID,
    EXT_KIND,
    KIND_CONFIRMED,
    KIND_TENTATIVE,
    CalendarPort,
)
from app.features.tasks.domains.appointment_chain.schemas import ChainConfig, ChainState
from pydantic import BaseModel

TENTATIVE_SUFFIX = " (예정)"


class ReconcileActionType(StrEnum):
    CREATED_TENTATIVE = "created_tentative"
    CONFIRMED = "confirmed"
    DELETED_DETECTED = "deleted_detected"
    NOTIFY_DUE = "notify_due"
    WAITING = "waiting"


class ReconcileAction(BaseModel):
    type: ReconcileActionType
    detail: str


def _tentative_summary(summary: str) -> str:
    return f"{summary}{TENTATIVE_SUFFIX}"


async def reconcile_chain(
    config: ChainConfig,
    state: ChainState,
    calendar: CalendarPort,
    *,
    chain_key: str,
    today: date,
) -> list[ReconcileAction]:
    """Reconcile one chain against ``calendar``. Mutates ``state`` in place.

    Args:
        config: Static settings from the task payload.
        state: Evolving cursor; mutated in place and persisted by the caller.
        calendar: The calendar port (fake or Google).
        chain_key: Stable id stamped onto events (``extendedProperties.chain_id``),
            typically the ScheduleConfig id.
        today: Reference date (injected for deterministic behaviour).
    """
    actions: list[ReconcileAction] = []

    # ── 1. Evaluate the tentative appointment we are currently tracking ──────
    if state.tentative_event_id is not None:
        tentative_date = state.tentative_date
        event = await calendar.get_event(calendar_id=config.calendar_id, event_id=state.tentative_event_id)

        if event is None or tentative_date is None:
            # The user deleted our tentative event (or the pointer is inconsistent).
            # Forget it; step 2 recreates.
            actions.append(
                ReconcileAction(
                    type=ReconcileActionType.DELETED_DETECTED,
                    detail=f"tentative event {state.tentative_event_id} vanished; will recreate",
                )
            )
            state.tentative_event_id = None
            state.tentative_date = None
        elif event.start_date != tentative_date:
            # The user dragged the tentative event -> confirm at its new date.
            await calendar.update_event(
                calendar_id=config.calendar_id,
                event_id=event.id,
                summary=config.summary,
                extended_private={EXT_CHAIN_ID: chain_key, EXT_KIND: KIND_CONFIRMED},
            )
            actions.append(
                ReconcileAction(
                    type=ReconcileActionType.CONFIRMED,
                    detail=f"user moved appointment to {event.start_date.isoformat()}; confirmed",
                )
            )
            state.anchor_date = event.start_date
            state.tentative_event_id = None
            state.tentative_date = None
        elif config.auto_confirm and today >= tentative_date:
            # The tentative date arrived untouched -> auto-confirm it.
            await calendar.update_event(
                calendar_id=config.calendar_id,
                event_id=event.id,
                summary=config.summary,
                extended_private={EXT_CHAIN_ID: chain_key, EXT_KIND: KIND_CONFIRMED},
            )
            actions.append(
                ReconcileAction(
                    type=ReconcileActionType.CONFIRMED,
                    detail=f"tentative date {tentative_date.isoformat()} passed; auto-confirmed",
                )
            )
            state.anchor_date = tentative_date
            state.tentative_event_id = None
            state.tentative_date = None
        else:
            # Still pending. Maybe it's time to notify.
            _maybe_notify(config, state, today, actions)
            actions.append(
                ReconcileAction(
                    type=ReconcileActionType.WAITING,
                    detail=f"tentative appointment on {tentative_date.isoformat()} awaiting user action",
                )
            )
            return actions

    # ── 2. Ensure a tentative appointment exists ─────────────────────────────
    if state.tentative_event_id is None:
        target = state.anchor_date + timedelta(days=config.interval_days)
        created = await calendar.create_event(
            calendar_id=config.calendar_id,
            summary=_tentative_summary(config.summary),
            start_date=target,
            extended_private={EXT_CHAIN_ID: chain_key, EXT_KIND: KIND_TENTATIVE},
        )
        state.tentative_event_id = created.id
        state.tentative_date = target
        state.last_notified_date = None  # reset so the new appointment can notify
        actions.append(
            ReconcileAction(
                type=ReconcileActionType.CREATED_TENTATIVE,
                detail=f"created tentative appointment on {target.isoformat()}",
            )
        )
        _maybe_notify(config, state, today, actions)

    return actions


def _maybe_notify(config: ChainConfig, state: ChainState, today: date, actions: list[ReconcileAction]) -> None:
    """Append a NOTIFY_DUE action if within the lead window and not already sent."""
    if config.notify_days_before is None or state.tentative_date is None:
        return
    notify_on_or_after = state.tentative_date - timedelta(days=config.notify_days_before)
    if today >= notify_on_or_after and state.last_notified_date != state.tentative_date:
        state.last_notified_date = state.tentative_date
        actions.append(
            ReconcileAction(
                type=ReconcileActionType.NOTIFY_DUE,
                detail=f"notification due for appointment on {state.tentative_date.isoformat()}",
            )
        )
