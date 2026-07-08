"""Runnable, no-setup demo of the appointment-chain reconcile loop.

Run it from the hub module (no DB, no Google, no credentials needed)::

    uv run --directory modules/hub python scripts/demo_reconcile.py

It simulates a "haircut" chain over several ticks, including the user dragging
the tentative appointment, and prints the calendar state after each tick so you
can watch the chain reschedule itself. Config comes from a ``ChainConfig`` (what
would live in a ScheduleConfig payload); the evolving ``ChainState`` is what the
task persists in the ``task_states`` table between ticks.
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Allow running as a plain script from the hub module (`python scripts/demo_reconcile.py`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.features.tasks.domains.appointment_chain.calendar.fake import FakeCalendarClient
from app.features.tasks.domains.appointment_chain.reconcile import reconcile_chain
from app.features.tasks.domains.appointment_chain.schemas import ChainConfig, ChainState

CHAIN_KEY = "demo-haircut"


async def _print_calendar(cal: FakeCalendarClient) -> None:
    events = await cal.list_events(calendar_id="primary")
    if not events:
        print("      (calendar empty)")
    for ev in events:
        print(f"      · {ev.start_date.isoformat()}  [{ev.kind:9}]  {ev.summary}")


async def _tick(label: str, config: ChainConfig, state: ChainState, cal: FakeCalendarClient, today: date) -> None:
    print(f"\n▶ {label}  (today = {today.isoformat()})")
    actions = await reconcile_chain(config, state, cal, chain_key=CHAIN_KEY, today=today)
    for action in actions:
        print(f"      → {action.type.value}: {action.detail}")
    print(
        f"    anchor={state.anchor_date.isoformat()}  "
        f"tentative={state.tentative_date.isoformat() if state.tentative_date else None}"
    )
    await _print_calendar(cal)


async def main() -> None:
    config = ChainConfig(
        summary="이발",
        interval_days=28,
        notify_days_before=3,
        auto_confirm=True,
        initial_anchor_date=date(2026, 7, 1),
    )
    state = ChainState(anchor_date=config.initial_anchor_date)
    cal = FakeCalendarClient()

    print("=" * 68)
    print("Appointment-chain reconcile demo — chain '이발', interval 28 days")
    print(f"Starting anchor (last haircut): {state.anchor_date.isoformat()}")
    print("=" * 68)

    # 1) First tick seeds a tentative appointment 4 weeks out.
    await _tick("Tick 1: seed", config, state, cal, today=date(2026, 7, 2))

    # 2) A later tick within the notify window fires a (deduped) notification.
    assert state.tentative_date is not None
    await _tick("Tick 2: near the date", config, state, cal, today=state.tentative_date - timedelta(days=2))

    # 3) The user drags the tentative appointment a few days earlier.
    moved_to = state.tentative_date - timedelta(days=5)
    print(f"\n✋ User drags the tentative appointment to {moved_to.isoformat()}")
    assert state.tentative_event_id is not None
    await cal.update_event(calendar_id="primary", event_id=state.tentative_event_id, start_date=moved_to)

    # 4) Reconcile confirms the move and schedules the NEXT one relative to it.
    await _tick("Tick 3: after the move", config, state, cal, today=moved_to + timedelta(days=1))

    # 5) Let the next appointment pass untouched -> auto-confirm + roll forward again.
    assert state.tentative_date is not None
    await _tick("Tick 4: next date passes untouched", config, state, cal, today=state.tentative_date)

    print("\n" + "=" * 68)
    print("Done. The chain kept exactly one tentative appointment alive the whole")
    print("time, and rescheduled itself around the user's manual move.")
    print("=" * 68)


if __name__ == "__main__":
    asyncio.run(main())
