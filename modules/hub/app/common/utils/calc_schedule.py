"""Utility helpers for schedule timing calculations.

Centralises the next-run-time logic so that both the dispatcher and the
schedule-config service can share it without creating circular imports.
"""

from datetime import UTC, datetime, timedelta

from croniter import croniter


def calc_next_run(
    cron_expression: str | None,
    interval_seconds: int | None,
    now: datetime | None = None,
) -> datetime:
    """Calculate the next run datetime from a cron expression or interval.

    Priority: ``cron_expression`` is evaluated first; ``interval_seconds`` is
    used only when ``cron_expression`` is absent.  Raises :exc:`ValueError`
    when neither is provided.

    Args:
        cron_expression: A valid cron expression (e.g. ``"0 9 * * 1-5"``), or
            ``None`` to fall back to *interval_seconds*.
        interval_seconds: A fixed delay in seconds from *now*, or ``None``.
        now: The reference datetime.  Defaults to the current UTC time when
            not supplied.

    Returns:
        The next :class:`~datetime.datetime` at which the schedule should run.

    Raises:
        ValueError: If both *cron_expression* and *interval_seconds* are
            ``None`` / falsy.
    """
    if now is None:
        now = datetime.now(UTC)

    if cron_expression:
        return croniter(cron_expression, now).get_next(datetime)
    if interval_seconds:
        return now + timedelta(seconds=interval_seconds)

    raise ValueError("Cannot calculate next run time: neither cron_expression nor interval_seconds is set.")
