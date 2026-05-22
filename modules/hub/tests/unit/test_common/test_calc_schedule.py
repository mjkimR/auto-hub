"""Unit tests for app.common.utils.calc_schedule.calc_next_run.

This module owns all behavioural tests for the shared scheduling utility,
since both DispatcherService and ScheduleConfigService delegate to it.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.common.utils.calc_schedule import calc_next_run


class TestCalcNextRun:
    """Behavioural tests for calc_next_run()."""

    NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)

    # ------------------------------------------------------------------
    # cron_expression
    # ------------------------------------------------------------------

    def test_cron_expression_returns_next_datetime(self):
        """A valid cron expression should return the next matching datetime via croniter."""
        now = datetime(2026, 5, 11, 8, 0, 0, tzinfo=UTC)  # Monday 08:00 UTC

        result = calc_next_run(cron_expression="0 9 * * 1-5", interval_seconds=None, now=now)

        assert isinstance(result, datetime)
        assert result > now
        assert result.hour == 9
        assert result.minute == 0

    def test_cron_takes_precedence_over_interval(self):
        """cron_expression must be evaluated before interval_seconds."""
        result = calc_next_run(
            cron_expression="*/5 * * * *",  # every 5 minutes
            interval_seconds=3600,
            now=self.NOW,
        )

        # cron-based: next tick within 5 minutes, NOT 1 hour away
        assert result <= self.NOW + timedelta(minutes=5)

    # ------------------------------------------------------------------
    # interval_seconds
    # ------------------------------------------------------------------

    def test_interval_seconds_returns_now_plus_interval(self):
        """When only interval_seconds is given, the result must equal now + interval."""
        interval = 300

        result = calc_next_run(cron_expression=None, interval_seconds=interval, now=self.NOW)

        assert result == self.NOW + timedelta(seconds=interval)

    # ------------------------------------------------------------------
    # default `now`
    # ------------------------------------------------------------------

    def test_default_now_uses_utc(self):
        """When `now` is omitted the function should default to the current UTC time."""
        before = datetime.now(UTC)
        result = calc_next_run(cron_expression=None, interval_seconds=60)
        after = datetime.now(UTC)

        assert before + timedelta(seconds=60) <= result <= after + timedelta(seconds=60)

    # ------------------------------------------------------------------
    # error cases
    # ------------------------------------------------------------------

    def test_neither_cron_nor_interval_raises_value_error(self):
        """Should raise ValueError when both arguments are None / falsy."""
        with pytest.raises(ValueError, match="neither cron_expression nor interval_seconds"):
            calc_next_run(cron_expression=None, interval_seconds=None, now=self.NOW)

    def test_zero_interval_treated_as_falsy_raises_value_error(self):
        """interval_seconds=0 is falsy and should raise ValueError, same as None."""
        with pytest.raises(ValueError):
            calc_next_run(cron_expression=None, interval_seconds=0, now=self.NOW)
