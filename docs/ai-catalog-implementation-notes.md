# AI Catalog Implementation Notes

Explains how AI Catalog is structured and functions in code from a developer's perspective.
Operational rules and contracts are documented in [AI Catalog Gateway](ai-catalogs.md).

## Overview

An AI Catalog is a **gateway** representing a single AI account or plan. Every unit of work sent to an AI requests admission to exactly one catalog.
Quota holds, recovery, and concurrency limits are governed by the catalog, not individual runs.

Quota models differ by provider.

| Provider | Quota Model | When Hub Detects Limit |
| --- | --- | --- |
| Codex | Usage window based on first dispatch. Short / long refresh cycles | **After receiving** a limit-exceeded reply |
| Jules | Concurrency limit + 24-hour rolling daily task limit (Pro: 100/day, 15 concurrent) | Counted locally **before dispatching** |

Therefore, catalog responsibilities are divided into two independent axes:

| Axis | Selection Key | Role |
| --- | --- | --- |
| Quota Policy (`QuotaPolicy`) | `catalog.kind` | When work can be dispatched, and how quota recovers |
| Execution Adapter (`ExecutionAdapter`) | `catalog.adapter` | How pipeline requests are dispatched and how replies are read |

## Architecture

```text
                          ┌──────────────── AICatalogService (gateway) ────────────────┐
PipelineRun delivery ───► │ 1. Common checks: enabled / not DISABLED·UNKNOWN / unexpired hold │
  key "delivery:<id>"     │ 2. policy.admit()      ← QuotaPolicy by kind                 │
                          │ 3. Concurrency check   ← active_dispatch_count (runs + sess) │
Jules session ──────────► │ 4. Record ledger on pass (ai_catalog_dispatches, once per key)│
  key "session:<id>"      │ → Returns Admission(rejection | None)                       │
                          └────────────────────────────────────────────────────────────┘
                                   │ Policy registry (kind)        │ Adapter registry (adapter)
                                   ▼                               ▼
                    codex → CodexWindowPolicy          codex-github-mention → CodexGithubMentionAdapter
                    jules → DailyQuotaPolicy           jules-api → 501 (PR pipeline unsupported)
```

### Module Map

| Path (`modules/hub/app/features/…`) | Responsibility |
| --- | --- |
| `ai_catalogs/models.py` | `AICatalog`, `AICatalogDispatch` (ledger), `AICatalogSession` (session tracking) |
| `ai_catalogs/services.py` | Gateway: locking, common rejections, concurrency check, ledger recording, hold / activation / config / connector management |
| `ai_catalogs/repos.py` | Queries and aggregations. `admits_dispatch()` (SQL version of common check), `active_dispatch_count()`, ledger query/recording |
| `ai_catalogs/policies/base.py` | `QuotaPolicy` protocol, `utc()`, `hold_state()` |
| `ai_catalogs/policies/codex_window.py` | Codex usage window, refresh cycle, recovery probe |
| `ai_catalogs/policies/daily_quota.py` | Daily task quota limit (`rolling` / `calendar`) |
| `ai_catalogs/policies/registry.py` | kind → policy mapping |
| `ai_catalogs/api/v1.py` | `/api/v1/ai-catalogs` |
| `project_management/pipeline_runs/adapters/base.py` | `ExecutionAdapter` protocol, `DeliveryTarget`, `DeliveryReceipt`, `AgentReply` |
| `project_management/pipeline_runs/adapters/codex_github_mention.py` | Post PR mention, re-align markers, parse Codex replies |
| `project_management/pipeline_runs/adapters/registry.py` | adapter → implementation mapping. Unimplemented adapters return 501 |
| `project_management/pipeline_runs/usecases/lifecycle.py` | Run state transitions and persistence; processes adapter results; resolves the project's catalog on enrollment and resume |
| `project_management/projects/services.py` | Validates a project's `github.ai_catalog_id` (only catalogs whose adapter supports pipeline delivery) |
| `hub-ui/…/ai-catalogs/catalog-kinds.ts` | Per-kind UI registry: policy dialog component, button label, card summary |
| `execution/tasks/domains/jules/client.py` | Jules REST v1alpha client |
| `execution/tasks/domains/jules/service.py` | Jules session initiation and synchronization |
| `execution/tasks/domains/jules/task.py` | Scheduled tasks `jules.session`, `jules.sync_sessions` |

## Core Concepts

### Admission

`AICatalogService.request_dispatch(session, catalog_id, run_id | None, dispatch_key, now)` returns `Admission(catalog, rejection)`. It never raises an exception.

1. **Common checks.** Rejects if the catalog is disabled, in a `disabled` or `unknown` state, or has an unexpired `quota_blocked` hold. The same criteria are represented in SQL by `AICatalogRepository.admits_dispatch()`, which is used when the scheduler queries dispatch targets. Both implementations must always be updated in tandem.
2. **Policy.** `policy.admit(session, catalog, dispatch_key, now)` applies recovery transitions and returns rejection reasons if needed.
3. **Concurrency.** `active_dispatch_count` must be strictly less than `policy.effective_concurrency`.
   - A pipeline run occupies a slot when it is `implementing`, or when it is `dispatching` and its active attempt is also `dispatching`.
   - A session occupies a slot until it reaches `completed` or `failed`.
4. **Ledger.** Once all checks pass, `reserve_dispatch()` records an entry in the ledger.

When rejected, the caller commits the transaction (`session.commit()`) before raising HTTP 409. This ensures state transitions made by the policy during evaluation (such as newly triggered daily holds or probe phase transitions) are preserved rather than rolled back.

### Dispatch Key and Ledger (`ai_catalog_dispatches`)

- Records one row per admitted unit of work. `dispatch_key` is unique.
  - Pipeline: `delivery:<ExecutionDelivery.id>`
  - Jules: `session:<AICatalogSession.id>`
- Retrying with the same key does not insert a new row and preserves the original record. Policies exclude their own key from quota calculation (`exclude_dispatch_key`).
- Entries older than 30 days are pruned when writing a new record for the same catalog.
- Currently, only `DailyQuotaPolicy` reads the ledger.

### Session Tracking (`ai_catalog_sessions`)

- Tracks provider sessions initiated by Hub outside the pull request pipeline until completion. Currently used only for Jules.
- The state remains `dispatching` until creation is confirmed; once confirmed, the provider's state is stored in lowercase.
- Result bodies are not stored; only URLs and pull request links are retained.

## Flows

### Pipeline Dispatch (`PipelineRunUseCase.dispatch_implementation`)

```text
Verify lease → Check project changes (if changed, BLOCKED without consuming slot)
→ resolve_execution_adapter()             # Raises 501 before admission if unimplemented
→ Query active attempt → Confirm delivery # Create if missing; create new delivery if already posted
→ request_dispatch(catalog, run, "delivery:<id>")
     ├ Rejected: commit → 409
     └ Passed: attempt = DISPATCHING
→ (Outside transaction) _guard_dispatch → adapter.deliver(observer, target, request, n, authorize)
→ Record delivery (external_id, posted_at, url) → IMPLEMENTING → record_dispatch_delivered()
```

During observation (`advance_run`), the flow proceeds as follows:
- `adapter.collect_replies()` returns a list of `AgentReply` objects. Lifecycle persists these as `ExecutionReply`.
- If a quota reply is present, increments `quota_block_count` on the run and calls `record_quota_event(catalog_id, observed_at)`.
- Silent retry thresholds utilize the adapter's `silent_timeout` and `silent_block_reason`.

### Jules Session Start (`JulesSessionService.start`)

```text
_catalog_access: verify kind == jules, connector(provider=jules, enabled) → decrypt token
→ _observe: refresh uncompleted sessions (finished sessions release slots)
→ request_dispatch(catalog, None, "session:<id>")
     ├ Rejected: commit → 409
     └ Passed: AICatalogSession(state=dispatching, title="<title> [hub-session:<id>]")
→ POST /v1alpha/sessions
     ├ Success: update name / state / url / outputs[].pullRequest.url
     ├ 429: mark session failed + record_quota_event (conservatively treated as reaching daily limit)
     ├ Other 4xx: mark session failed
     └ 5xx / Network error: remain dispatching → reconciled later by title
```

Processing in `_observe`:
- Sessions with an external name (`external_name`) are updated via `GET sessions/{id}`.
- Sessions lacking an external name are reconciled by scanning recent sessions via `find_session_by_title` (latest 3 pages × 100 items).
- Sessions that remain unlocated after 1 hour are marked as `failed`.
- Lookup errors are ignored so observation failures do not prevent starting new tasks.

## Policy Summary

Detailed rules are documented in [AI Catalog Gateway](ai-catalogs.md). Here, only implementation details are highlighted.

### `CodexWindowPolicy`

- Configuration is `CodexWindowConfig`: `short_refresh_enabled`, `short_refresh_cycle_minutes`, `long_refresh_cycle_minutes`, `probe_window_minutes`. Defaults are populated upon saving.
- Runtime state is `CodexWindowState` (`probe_started_at`, `short_refresh_failure_count`, `last_refreshed_at`, `usage_window_started_at`), stored whole in `ai_catalogs.policy_state`. Each hook loads it, mutates it, and reassigns the dumped value (`_store`), because JSON columns track reassignment rather than in-place mutation.
- `on_availability_override`: A manual hold or enable switch drops an unfinished probe.
- `admit`: Transitions to `probe` if the hold has expired, or cleans up completed probes. Does not reject on its own.
- `on_delivered`: Records usage window start time and probe start time.
- `on_quota_signal`: Applies a hold based on short cycle or long cycle with added jitter.
- `on_hold_cleared`: Updates `last_refreshed_at` and resets the usage window.

### `DailyQuotaPolicy`

- Configuration is `DailyQuotaConfig`: `daily_task_limit`, `window` (`rolling` default / `calendar`), `timezone`.
- `admit`:
  - Transitions back to `normal` if hold has expired. No probe phase.
  - If the count of ledger entries within the window meets or exceeds the limit, applies a hold with jitter targeting the moment a slot opens and rejects admission.
- Slot release timestamp calculation:
  - `rolling`: Sorted ascending within window: `admitted[n - limit] + 24h`
  - `calendar`: Next local midnight. Adding one day to a zone-aware date naturally handles DST transitions.
- `on_quota_signal`:
  - `rolling`: 24-hour hold starting from provider rejection timestamp (external tasks outside hub are not recorded in the ledger).
  - `calendar`: Hold until next midnight.
- `effective_concurrency` equals `configured_concurrency`.

## Data Models

**`ai_catalogs`**

| Column | Description |
| --- | --- |
| `key`, `name`, `kind`, `adapter` | Identification info and policy/adapter selection |
| `connector_id` | Credentials for providers called directly by Hub (Jules). Codex uses the project's GitHub connection |
| `enabled`, `availability_state`, `available_at`, `availability_*` | Common gate state |
| `configured_concurrency`, `refresh_jitter_minutes` | Common configuration |
| `policy_config` (JSON) | Configuration validated by the kind policy |
| `policy_state` (JSON) | Runtime quota state owned by the kind policy (Codex usage window, probe, short-cycle failures) |

**`projects.ai_catalog_id`**: Catalog for the project's pull request work, exposed as `github.ai_catalog_id`. Empty selects `personal-codex`.

**`execution_deliveries.external_id`, `execution_replies.external_id`**: The provider's identifier returned by the adapter (a GitHub comment ID for Codex mentions).

**`ai_catalog_dispatches`**: `ai_catalog_id`, `dispatch_key` (unique), `admitted_at`. Index on `(ai_catalog_id, admitted_at)`.

**`ai_catalog_sessions`**: `ai_catalog_id`, `schedule_config_id`, `title`, `state`, `external_name` (unique), `url`, `pull_request_url`, `failure_detail`, `observed_at`

**Seed Data**
- `personal-codex` (codex / codex-github-mention)
- `personal-jules` (jules / jules-api, concurrency 15, daily limit 100 rolling, no connector)

## API

| Method | Path (`/api/v1/ai-catalogs`) | Description |
| --- | --- | --- |
| GET | `` | List catalogs. Includes `effective_concurrency`, `held_run_count`, `active_dispatch_count`, `open_session_count`, and the capability flags `connector_provider` and `pipeline_delivery` |
| GET | `/{key}/sessions?offset=&limit=` | A page of tracked sessions, most recent first, with `total_count` (default limit 50, max 100). Ties on `created_at` are broken by `id`, so pages never overlap |
| PUT / DELETE | `/{key}/availability` | Manually set / clear hold |
| PUT | `/{key}/enabled` | Enable or disable catalog |
| PUT | `/{key}/policy-config` | Validate and normalize via kind policy's `validate_config()` before saving |
| PUT | `/{key}/connector` | Only allows connectors for matching provider (`CATALOG_CONNECTOR_PROVIDERS`) |

Scheduled Tasks:
- `jules.session`
  - payload: `catalog_key`, `repository` (`owner/repo`), `starting_branch`, `title`, `prompt`, `auto_create_pr`
- `jules.sync_sessions`
  - payload: `catalog_key`
  - Keep interval short because releasing concurrency slots after session termination depends on this task's frequency.

Connector providers are `github`, `jules`, `linear`. For `jules`, the API key is stored in `token`.

## Design Decisions

| Decision | Rationale |
| --- | --- |
| Separate registries for policies and adapters | Quota models and execution mechanisms evolve independently across providers (e.g. Jules uses a quota policy without a PR pipeline adapter). |
| Return rejection as a value, commit then 409 | Rejecting via exception would roll back hold and probe transitions recorded by the policy during admission. |
| Confirm pipeline delivery **before** admission | The ledger key (`delivery:<id>`) must remain idempotent across retries to prevent duplicate counting. |
| Return 501 for unimplemented adapters **before** admission | Prevents tasks that cannot be executed from consuming quota and concurrency slots. |
| Use Jules for scheduled sessions rather than PR pipelines | The Jules API (v1alpha) cannot push to existing PR branches; `AUTO_CREATE_PR` always creates a new branch and PR. |
| Include `[hub-session:<id>]` in Jules session title | Jules session creation API lacks idempotency keys; titles enable reconciling uncertain creations. |
| Treat Jules 429 as quota events | Provider rate-limit error payload schema is undocumented; waiting conservatively is safer, and operators can manually clear holds. |
| Default daily quota window to `rolling` | Jules official documentation specifies a "rolling 24 hour window". |
| Codex runtime state in `policy_state` JSON | Kind-specific state stays off the shared table. The policy validates it through a Pydantic model and replaces the whole value under the catalog row lock. |
| Capability flags instead of kind names in the UI | The UI shows connector and session controls from `connector_provider`, and offers project catalogs from `pipeline_delivery`, so new kinds need no UI branching for those controls. |
| Project-level catalog selection, applied on resume | Enrollment uses the project's catalog; a resume starts a new attempt, so it adopts the project's current selection without splitting one delivery across catalogs. |

## Extension Guide

**Adding a New Quota Model (`kind`)**
1. Add a new value to `AICatalogKind`.
2. Implement `QuotaPolicy` (including `validate_config`). Define config as a Pydantic model with `extra="forbid"`.
3. Register the policy in `policies/registry.py`.
4. If Hub calls the provider directly, add the provider to `CATALOG_CONNECTOR_PROVIDERS` and `ConnectorProvider`.
5. Add a policy dialog component (props: `CatalogDialogProps`) and register it in `catalogKinds` in `catalog-kinds.ts`.

**Adding a New Pipeline Execution Adapter (`adapter`)**
1. Implement `ExecutionAdapter`: `deliver`, `collect_replies`, `silent_timeout`, `silent_block_reason`.
2. Register it in `_ADAPTERS` in `adapters/registry.py`. If under development, place it in `_NOT_IMPLEMENTED`.

**Session-based Work Outside the Pipeline**
- Follow the pattern in `jules/service.py`: Sync → `request_dispatch(..., None, "session:<id>")` → create session record → execute external call → persist result.

## Testing

| Location | Target |
| --- | --- |
| `tests/unit/test_ai_catalogs/test_refresh_policy.py` | Gateway admission, rejection return, ledger recording conditions, Codex policy rules |
| `tests/unit/test_ai_catalogs/test_daily_quota_policy.py` | Rolling and calendar boundaries, reduced limits, clearing holds, provider rejection, config validation |
| `tests/unit/test_pipeline_runs/test_lifecycle.py` | Commit then raise on rejection, adapter resolution (501/409), quota reply handling |
| `tests/e2e/test_ai_catalogs/test_ai_catalogs_api.py` | Per-kind validation for policy-config and connector APIs, session listing, capability flags |
| `tests/e2e/test_ai_catalogs/test_jules_sessions.py` | Jules session creation, ledger, daily holds, 429 handling, reconciliation (using `httpx.MockTransport`) |
| `tests/e2e/test_projects/test_pipeline_runs_api.py` | Pipeline integration including idempotent ledger records across retried deliveries and project catalog selection |
| `modules/hub-ui/…/ai-catalogs/AICatalogsView.test.ts` | Per-kind policy editors, capability-driven controls, policy/connector saving, timezone validation, session listing |

- Catalogs in unit tests are `MagicMock(spec=AICatalog)` instances, so `kind`, `policy_config`, and `policy_state` must be populated. `test_refresh_policy.py` builds Codex state with `make_catalog(**state)` and reads it back with `state_of()`.
- UI dialogs mount when opened and move focus once while opening; tests should type multi-character values after the dialog has settled.
- Lifecycle unit tests monkeypatch `resolve_execution_adapter`.
- Compare new migrations against models with `alembic check`. SQLite cannot run the complete migration chain due to prior migrations, so verify against PostgreSQL.

## Known Limitations and Remaining Work

### External Facts to Verify

- [ ] **Exact meaning of Jules 429.** Cannot distinguish daily limit vs. concurrency limit. Currently applies a 24-hour rolling hold in both cases. Requires inspecting actual responses to separate behaviors.
- [ ] **Definition of one Jules "task".** Unclear whether `sendMessage` or repeated PR comments count toward the daily limit.
- [ ] **Jules behavior at concurrency limit.** Unclear whether requests queue (`QUEUED`) or reject immediately.
- [ ] **Completion without output.** Cases of `COMPLETED` status without `outputs` have been observed; currently treated as normal completion.
- [ ] **Live invocation verification.** Execute live runs of the real Jules API and post-refactor Codex pipeline end-to-end.

### Code

- [ ] Sessions in `AWAITING_PLAN_APPROVAL` or `AWAITING_USER_FEEDBACK` states continue to hold concurrency slots; approval or feedback is not automated.
- [ ] Title-based reconciliation only checks the latest 300 sessions. Unconfirmed sessions older than that fail after 1 hour.
- [ ] The session list pages by offset but has no filtering (for example by state or schedule).
- [ ] 30-day ledger cleanup only runs when inserting new records.
- [ ] Catalogs are selected per project. Choosing a catalog per pull request or task is deferred until a router decides where each piece of work goes.
- [ ] Integrating Jules into the PR pipeline has two alternatives to choose between when needed:
  - Hub applies `changeSet.gitPatch` to the PR branch
  - Track child PRs created by Jules
- [ ] `alembic check` reports 2 comment discrepancies with models: `pipeline_runs.pull_snapshot`, `schedule_configs.next_run_at`. Unrelated to AI Catalog.
