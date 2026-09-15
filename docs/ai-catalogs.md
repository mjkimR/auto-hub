# AI Catalog Gateway

## Status

An AI catalog is the gateway for one AI account or plan. Every AI-bound unit of
work asks exactly one catalog for admission, and the catalog owns quota holds,
recovery, and concurrency for all of its work.

Two catalogs are seeded:

| Key | Kind | Adapter | Used by |
| --- | --- | --- | --- |
| `personal-codex` | `codex` | `codex-github-mention` | The pull request pipeline (every enrolled run) |
| `personal-jules` | `jules` | `jules-api` | Scheduled Jules sessions (`jules.session`); pull request delivery is not implemented (501) |

The change history and open work for this design are summarized in
[AI Catalog generalization worklog (2026-09-15, Korean)](ai-catalogs-worklog-2026-09-15.md).

## Why a catalog is the gateway

A quota is attached to an AI account and its capacity, not to a pipeline run.
Likewise, a concurrency limit is meaningful only across all work sharing the
same account. If runs owned their own retry timestamps they could race, retry
together after a reset, and defeat the intended safety limit.

Work therefore never calculates quota retry times. It submits an admission
request, and the catalog either admits it or returns a rejection until its
shared gate opens.

```text
Pipeline delivery ("delivery:<id>") ─┐
                                     ├─► AI Catalog gateway ─► quota policy (by kind)
Jules session     ("session:<id>")  ─┘     shared checks        codex → CodexWindowPolicy
                                           concurrency           jules → DailyQuotaPolicy
                                           dispatch ledger
```

## Two independent axes

| Axis | Selected by | Contract | Implementations |
| --- | --- | --- | --- |
| Quota policy | `kind` | `ai_catalogs/policies/base.py` `QuotaPolicy` | `CodexWindowPolicy`, `DailyQuotaPolicy` |
| Execution adapter (pipeline) | `adapter` | `pipeline_runs/adapters/base.py` `ExecutionAdapter` | `CodexGithubMentionAdapter`; `jules-api` is reserved and returns 501 |

A policy decides when work may start and how quota recovers. An adapter
delivers a pipeline request and reads the agent's replies. Neither mutates the
other's state; the pipeline lifecycle owns run state and persistence.

## Catalog model

| Field | Responsibility |
| --- | --- |
| `id`, `key`, `name` | Stable identity and operator-facing label |
| `kind`, `adapter` | Quota policy and execution adapter |
| `connector_id` | Credentials for a provider the hub calls directly (a `jules` connector); Codex uses each project's GitHub connection |
| `enabled` | Operator switch; a disabled catalog admits nothing |
| `configured_concurrency` | Normal maximum concurrent work |
| `effective_concurrency` (read-only) | Current maximum from the policy (Codex: `1` in probe; a kind without a policy: `0`) |
| `availability_state` | `normal`, `quota_blocked`, `probe`, `disabled`, or `unknown` |
| `available_at` | Earliest UTC admission time of the current hold; kept while disabled |
| `availability_source`, `availability_note`, `availability_updated_at` | Operator-visible evidence and audit metadata |
| `refresh_jitter_minutes` | Safety delay added to every calculated reset (default 10) |
| `policy_config` | Kind-specific quota settings, validated and normalized by the kind's policy |
| `probe_started_at`, `short_refresh_failure_count`, `last_refreshed_at`, `usage_window_started_at` | Codex usage-window runtime state |
| `held_run_count`, `active_dispatch_count` (read-only) | Pipeline runs queued/dispatching/implementing; runs and sessions currently holding capacity |
| `revision` | Optimistic state/configuration revision |

A pipeline run records only its `ai_catalog_id` and `quota_block_count`.

## Gateway decisions

```text
request_dispatch(catalog_id, run_id | None, dispatch_key, now) -> Admission(catalog, rejection | None)
record_dispatch_delivered(catalog_id, posted_at)
record_quota_event(catalog_id, observed_at)
set_availability / clear_availability / set_enabled / update_policy_config / set_connector
```

1. **Shared checks.** A catalog that is disabled, `disabled`, `unknown`, or
   holding an unexpired `quota_blocked` hold rejects the request. The same rule
   is expressed in SQL (`AICatalogRepository.admits_dispatch`) so the scheduler
   does not select dispatching runs whose catalog cannot admit them. Only
   dispatch is gated: CI, pushes, merges, and quota replies keep being observed
   during a hold.
2. **Policy.** `policy.admit()` applies recovery transitions and may return a
   rejection (for example a daily cap just reached).
3. **Capacity.** Work holding capacity must be below `effective_concurrency`.
   A pipeline run holds capacity while `implementing`, or while `dispatching`
   with an admitted (possibly uncertain) delivery; a run only waiting for
   admission holds nothing. A tracked session holds capacity until it is
   `completed` or `failed`.
4. **Ledger.** Admitted work is recorded once in `ai_catalog_dispatches` under
   its `dispatch_key`; a retry keeps the first entry and a policy never counts a
   key against itself. Entries older than 30 days are pruned when the catalog
   records new work.
5. **Rejections are returned, not raised.** The caller commits what the policy
   recorded while rejecting (a new hold, a probe transition) and then answers
   409. Pipeline deliveries are settled before admission so the ledger key is
   stable across retries.
6. **No silent failover.** A disabled or unknown catalog never falls back to a
   different model or account.

A pipeline run on a project that was disabled, edited, or lost its GitHub
connection after enrollment is moved to `blocked` before admission and takes no
capacity.

## Codex policy (`CodexWindowPolicy`)

`policy_config` (defaults filled on save):

```json
{"short_refresh_enabled": true, "short_refresh_cycle_minutes": 300,
 "long_refresh_cycle_minutes": 10080, "probe_window_minutes": 10}
```

1. When an expired hold is admitted, the catalog enters `probe`, sets
   `last_refreshed_at` to the hold end, and limits effective concurrency to one.
   The probe window starts only when that mention is delivered.
2. A delivered probe that runs `probe_window_minutes` without a quota event
   returns the catalog to `normal` and resets the short-cycle failure count,
   evaluated at the next admission or quota observation.
3. Codex resets a usage window a fixed time after its first task. Each
   delivered mention opens a new window when none is open or the previous one
   has lasted a full window; a probe and a cleared hold always start a new one.
   A mention posted before `last_refreshed_at` belongs to the old window.
4. A quota reply waits `cycle + jitter` from `usage_window_started_at`, or from
   the reply time when no window start inside the current window is known, so a
   hold is never released early. With the short cycle enabled, the first two
   consecutive failed refreshes use the short cycle and later ones the long
   cycle; with it disabled, every hold uses the long cycle.
5. A reply observed before the current hold ends, or before the latest refresh
   or manual clear, is already accounted for: it neither consumes a short retry
   nor moves a hold earlier.
6. Codex never rejects before capacity is checked; its exhaustion is known only
   from replies.

## Daily quota policy (`DailyQuotaPolicy`, Jules)

`policy_config`:

```json
{"daily_task_limit": 100, "window": "rolling", "timezone": "UTC"}
```

- `rolling` counts ledger entries in the last 24 hours. This matches Jules'
  documented "rolling 24 hour window" (Pro: 100 tasks per day, 15 concurrent).
  `calendar` counts from local midnight in `timezone`, for providers that reset
  by day.
- When the count reaches the limit, admission records a `quota_blocked` hold
  until the window next has room (plus jitter) and rejects. An expired hold
  resumes directly to `normal` when the window has room; there is no probe.
- `configured_concurrency` is the parallel cap.
- A provider refusal (`record_quota_event`) holds for a full window from the
  refusal on `rolling` (tasks started outside the hub are invisible to the
  ledger), or until the next midnight on `calendar`.
- A catalog without a valid `policy_config` is not admitted (409).

## Jules scheduled sessions

Jules cannot push to an existing pull request branch, so it runs scheduled
report and hygiene sessions instead of pipeline work. The hub tracks only
session state and links in `ai_catalog_sessions`; results stay in Jules or in
the pull requests it opens.

| Task | Payload | Behavior |
| --- | --- | --- |
| `jules.session` | `catalog_key`, `repository` (`owner/repo`), `starting_branch`, `title`, `prompt`, `auto_create_pr` | Refreshes unfinished sessions, asks for admission under `session:<id>`, then creates one Jules session |
| `jules.sync_sessions` | `catalog_key` | Refreshes unfinished sessions so finished ones release concurrency |

- The catalog needs an enabled `jules` connector whose credentials hold the API
  key as `token`.
- Session creation has no idempotency key. The hub titles each session
  `<title> [hub-session:<id>]`. An unconfirmed create (network or 5xx failure)
  stays `dispatching` and is adopted by title on a later run; one not found
  after an hour is marked `failed`.
- A 429 on create marks the session `failed` and is recorded as a quota event.
  Jules does not document its limit error, so this is conservative.
- Any other 4xx marks the session `failed`.

## Operator controls

**Settings → AI Catalogs** is the authoritative UI:

- set a local reset time, clear a hold, and enable or disable a catalog;
- edit the Codex refresh policy or the Jules quota policy (both saved through
  `PUT /api/v1/ai-catalogs/{key}/policy-config`);
- assign a Jules connector (`PUT /api/v1/ai-catalogs/{key}/connector`).

An explicit reset time replaces `available_at` for every piece of work on the
catalog, even while disabled. Clearing a hold records a refresh at that moment;
for Codex, older quota evidence and mentions are ignored and the next delivery
opens a new usage window.

The optional `just sync-codex-quota` helper reads a signed-in local Codex
account and sends the verified reset to the `personal-codex` availability
endpoint. It never sends credentials, raw account payloads, or run identifiers,
and fails closed when it cannot identify one blocking window.

## Adding a kind or adapter

1. Implement `QuotaPolicy` (including `validate_config`) and register it in
   `ai_catalogs/policies/registry.py`.
2. For pipeline work, implement `ExecutionAdapter` and register it in
   `pipeline_runs/adapters/registry.py`. Leave unfinished adapters in
   `_NOT_IMPLEMENTED` so they fail before admission.
3. If the hub calls the provider directly, map the kind to a connector provider
   in `CATALOG_CONNECTOR_PROVIDERS`.
4. Seed or create the catalog, add its settings form to the AI Catalogs view,
   and cover the policy with unit tests and the integration with e2e tests.
