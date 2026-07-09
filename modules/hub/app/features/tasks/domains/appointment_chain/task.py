"""Dispatchable task that reconciles one appointment chain.

Design: one ScheduleConfig == one chain. Create a ScheduleConfig with
``task_func="calendar.reconcile_chain"``, an interval/cron for how often to poll,
and a ``payload`` matching :class:`ChainConfig` (summary, interval_days, ...).

Each dispatcher tick then:
  1. reads the chain's config straight from the payload,
  2. loads the chain's evolving state from the generic ``task_states`` store
     (keyed by this ScheduleConfig's id, taken from the task context),
  3. reconciles against the calendar and writes the new state back.

The reconcile logic itself lives in
:mod:`app.features.tasks.domains.appointment_chain.reconcile`.
"""

from datetime import UTC, date, datetime
from uuid import UUID

from app.features.task_states import store as task_state_store
from app.features.tasks import task
from app.features.tasks.core.context import get_task_meta
from app.features.tasks.core.log import logger
from app.features.tasks.domains.appointment_chain.calendar import get_calendar_client
from app.features.tasks.domains.appointment_chain.reconcile import ReconcileAction, ReconcileActionType, reconcile_chain
from app.features.tasks.domains.appointment_chain.schemas import ChainConfig, ChainState
from app_layer_base.core.database.transaction import AsyncTransaction


@task(name="calendar.reconcile_chain")
async def reconcile_chain_task(payload: ChainConfig) -> None:
    meta = get_task_meta()
    if meta is None:
        raise RuntimeError("calendar.reconcile_chain must run inside a task context (needs the config id).")
    await run_reconcile(payload, config_id=meta.config_id, today=datetime.now(UTC).date())


async def run_reconcile(config: ChainConfig, *, config_id: UUID, today: date) -> list[ReconcileAction]:
    """Load state, reconcile, persist state. Returns the actions taken.

    Kept separate from the ``@task`` wrapper so it can be driven directly (with an
    explicit ``config_id`` and ``today``) in tests without a dispatcher context.
    """
    calendar = get_calendar_client()

    async with AsyncTransaction() as session:
        raw = await task_state_store.load(session, config_id)
        state = ChainState(**raw) if raw is not None else ChainState(anchor_date=config.initial_anchor_date)

        actions = await reconcile_chain(config, state, calendar, chain_key=str(config_id), today=today)

        await task_state_store.upsert(session, config_id, state.model_dump(mode="json"))
        await session.commit()

    for action in actions:
        if action.type is ReconcileActionType.NOTIFY_DUE:
            # TODO: deliver via a real notifier (Telegram/email). For now, log it.
            logger.warning(f"NOTIFY: {action.detail}")
        else:
            logger.info(f"{action.type.value}: {action.detail}")

    return actions
