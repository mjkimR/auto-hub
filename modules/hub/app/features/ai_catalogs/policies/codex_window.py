from datetime import datetime, timedelta

from app.features.ai_catalogs.models import AICatalog, AICatalogState
from app.features.ai_catalogs.policies.base import hold_state, utc
from app.features.project_management.projects.services import ProjectError
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

SHORT_REFRESH_FAILURE_LIMIT = 2


class CodexWindowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    short_refresh_enabled: bool = True
    short_refresh_cycle_minutes: int = Field(default=300, ge=1, le=43_200)
    long_refresh_cycle_minutes: int = Field(default=10_080, ge=1, le=525_600)
    probe_window_minutes: int = Field(default=10, ge=1, le=1_440)


class CodexWindowState(BaseModel):
    """Usage-window runtime state kept in ``catalog.policy_state``."""

    probe_started_at: datetime | None = None
    short_refresh_failure_count: int = 0
    last_refreshed_at: datetime | None = None
    usage_window_started_at: datetime | None = None


class CodexWindowPolicy:
    """Codex resets a usage window a fixed time after its first task and reports exhaustion only by reply.

    A hold therefore waits a short or long refresh cycle from the window's first task, and an expired hold
    resumes through a single-task recovery probe.
    """

    def effective_concurrency(self, catalog: AICatalog) -> int:
        return 1 if catalog.availability_state == AICatalogState.PROBE else catalog.configured_concurrency

    def validate_config(self, config: dict) -> dict:
        try:
            return CodexWindowConfig.model_validate(config).model_dump()
        except ValidationError as exc:
            raise ProjectError(422, f"Invalid Codex refresh policy: {exc.errors()[0]['msg']}") from None

    @staticmethod
    def _config(catalog: AICatalog) -> CodexWindowConfig:
        try:
            return CodexWindowConfig.model_validate(catalog.policy_config)
        except ValidationError:
            raise ProjectError(409, "AI catalog has an invalid Codex refresh policy; save it again") from None

    @staticmethod
    def _state(catalog: AICatalog) -> CodexWindowState:
        try:
            return CodexWindowState.model_validate(catalog.policy_state or {})
        except ValidationError:
            raise ProjectError(409, "AI catalog has invalid Codex usage-window state; clear its hold") from None

    @staticmethod
    def _store(catalog: AICatalog, state: CodexWindowState) -> None:
        # JSON columns track reassignment, not in-place mutation, so the whole state is replaced.
        stored = state.model_dump(mode="json")
        if stored != catalog.policy_state:
            catalog.policy_state = stored

    @staticmethod
    def _usage_window(config: CodexWindowConfig) -> timedelta:
        # A long-cycle-only plan has no short window, so its usage window is the long cycle.
        minutes = (
            config.short_refresh_cycle_minutes if config.short_refresh_enabled else config.long_refresh_cycle_minutes
        )
        return timedelta(minutes=minutes)

    @staticmethod
    def _settle_probe(catalog: AICatalog, state: CodexWindowState, config: CodexWindowConfig, now: datetime) -> None:
        """Finish a delivered probe whose window passed without a quota event.

        Derived from persisted fields, so a transition lost to a rolled-back transaction is re-applied later.
        """
        if (
            catalog.availability_state == AICatalogState.PROBE
            and state.probe_started_at is not None
            and now - utc(state.probe_started_at) >= timedelta(minutes=config.probe_window_minutes)
        ):
            catalog.availability_state = AICatalogState.NORMAL
            catalog.available_at = None
            catalog.availability_note = "Recovery probe completed; normal catalog concurrency restored"
            catalog.revision += 1
            state.probe_started_at = None
            state.short_refresh_failure_count = 0

    async def admit(self, session: AsyncSession, catalog: AICatalog, dispatch_key: str, now: datetime) -> str | None:
        # Codex reports exhaustion only after a task runs, so it never rejects before capacity is checked.
        config, state = self._config(catalog), self._state(catalog)
        if catalog.availability_state == AICatalogState.QUOTA_BLOCKED and catalog.available_at is not None:
            # The gateway admits only an expired hold, which resumes through a recovery probe.
            catalog.availability_state = AICatalogState.PROBE
            catalog.revision += 1
            # The observation window and the next usage window both start when the probe is delivered.
            state.probe_started_at = None
            state.usage_window_started_at = None
            state.last_refreshed_at = utc(catalog.available_at)
        else:
            self._settle_probe(catalog, state, config, now)
        self._store(catalog, state)
        return None

    async def on_delivered(self, session: AsyncSession, catalog: AICatalog, posted_at: datetime) -> None:
        """Track the first task of the provider usage window and start a pending probe window."""
        config, state = self._config(catalog), self._state(catalog)
        if state.last_refreshed_at is not None and posted_at < utc(state.last_refreshed_at):
            # A reconciled mention posted before the latest hold ended or was cleared belongs to the old window;
            # it can neither anchor the next window nor stand in for the probe.
            return
        changed = False
        window_started_at = state.usage_window_started_at
        if window_started_at is None or posted_at >= utc(window_started_at) + self._usage_window(config):
            # The previous window has reset, so this delivery is the first task of a new one.
            state.usage_window_started_at = posted_at
            changed = True
        if catalog.availability_state == AICatalogState.PROBE and state.probe_started_at is None:
            state.probe_started_at = posted_at
            changed = True
        if changed:
            catalog.revision += 1
            self._store(catalog, state)

    async def on_quota_signal(
        self, session: AsyncSession, catalog: AICatalog, observed_at: datetime, now: datetime
    ) -> None:
        """Apply the catalog's refresh-cycle policy after a quota observation."""
        config, state = self._config(catalog), self._state(catalog)
        self._settle_probe(catalog, state, config, observed_at)
        covered_until = catalog.available_at or state.last_refreshed_at
        if covered_until is not None and observed_at < utc(covered_until):
            # Evidence from before the current hold or latest refresh is already accounted for: it must not
            # consume another short retry or move a verified hold earlier.
            self._store(catalog, state)
            return
        use_short_cycle = (
            config.short_refresh_enabled and state.short_refresh_failure_count < SHORT_REFRESH_FAILURE_LIMIT
        )
        if use_short_cycle:
            cycle_minutes = config.short_refresh_cycle_minutes
            state.short_refresh_failure_count += 1
            cycle_name = "short"
        else:
            cycle_minutes = config.long_refresh_cycle_minutes
            cycle_name = "long"
        # Without a known start inside the current window, the observation is the latest possible start,
        # which never releases the hold early.
        refresh_anchor = observed_at
        if state.usage_window_started_at is not None:
            window_started_at = utc(state.usage_window_started_at)
            if window_started_at <= observed_at < window_started_at + self._usage_window(config):
                refresh_anchor = window_started_at
        catalog.available_at = refresh_anchor + timedelta(minutes=cycle_minutes + catalog.refresh_jitter_minutes)
        catalog.availability_source = f"quota-{cycle_name}-cycle"
        catalog.availability_state = hold_state(catalog)
        catalog.availability_note = (
            f"Codex reported a usage limit; waiting for the {cycle_name} cycle from the window's first task"
        )
        catalog.availability_updated_at = now
        catalog.revision += 1
        state.probe_started_at = None
        self._store(catalog, state)

    async def on_hold_cleared(self, session: AsyncSession, catalog: AICatalog, now: datetime) -> None:
        # The operator reports a reset: older quota evidence is spent and the next delivery opens a new window.
        state = self._state(catalog)
        state.probe_started_at = None
        state.last_refreshed_at = now
        state.usage_window_started_at = None
        self._store(catalog, state)

    async def on_availability_override(self, session: AsyncSession, catalog: AICatalog, now: datetime) -> None:
        # A manual hold or enable switch replaces any recovery probe in progress.
        state = self._state(catalog)
        state.probe_started_at = None
        self._store(catalog, state)
