# AI Catalog Gateway

## Status

The seeded `personal-codex` record is the initial **AI Catalog gateway**. It
owns dispatch admission, quota block state, probe recovery, and per-run quota
block counts. The persistence table, API, run reference, and UI are all named
AI Catalog. A separate adapter/credential-binding entity (for example
`connector_ids`) remains a future extraction once a second adapter is
introduced.

## Why a catalog is the gateway

A quota is attached to an AI account and its capacity, not to a pipeline run.
Likewise, a concurrency limit is meaningful only across every task sharing the
same account/model route. If runs own their own retry timestamps they can race,
retry together after a reset, and defeat the intended safety limit.

Every AI-bound task therefore submits a dispatch request to exactly one
catalog. The catalog decides whether to dispatch now or reject the request
until its shared gate opens. Tasks do not calculate quota retry times.

```text
Pipeline run / attempt
        │ request dispatch
        ▼
AI Catalog Gateway ── adapter binding ── Codex GitHub mention / Jules / API model
  capacity leases
  global block window
  recovery probe
  per-run quota block count
```

## Catalog model

| Field | Responsibility |
| --- | --- |
| `id`, `key`, `name` | Stable catalog identity and operator-facing label |
| `kind`, `adapter` | Execution integration selected by the catalog |
| `enabled` | Operator switch; a disabled catalog admits no dispatch |
| `configured_concurrency` | Normal maximum concurrent external executions |
| `effective_concurrency` (read-only) | Current maximum, reduced to `1` in recovery probe mode |
| `availability_state` | `normal`, `quota_blocked`, `probe`, `disabled`, or `unknown` |
| `available_at` | Earliest UTC dispatch time of the current hold; kept while disabled |
| `short_refresh_enabled`, `short_refresh_cycle_minutes` | Whether to use the short cycle and its configurable interval (default: 5 hours) |
| `long_refresh_cycle_minutes` | Configurable long-cycle interval after short retries are exhausted (default: 1 week) |
| `refresh_jitter_minutes` | Fixed safety delay added to every calculated cycle boundary (default: 10 minutes) |
| `usage_window_started_at` | Delivery time of the first task in the current provider usage window; the quota wait anchor |
| `last_refreshed_at`, `short_refresh_failure_count` | End of the latest hold or manual clear (older quota evidence and mentions are ignored) and consecutive short-cycle failure count |
| `availability_source`, `availability_note`, `availability_updated_at` | Safe operator-visible evidence and audit metadata |
| `probe_started_at`, `probe_window_minutes` | Delivery time of the recovery probe and its observation window (10 minutes) |
| `held_run_count`, `active_run_count` (read-only) | Runs queued/dispatching/implementing, and runs currently holding capacity |
| `revision` | Optimistic state/configuration revision |

Catalog state is global. A pipeline run records only its `ai_catalog_id` and
`quota_block_count`. It does not own a quota-derived retry timestamp, and the
reason a dispatch was rejected is returned to the caller rather than stored on
the run.

## Gateway decisions

The catalog service exposes these operations to the scheduler and adapters:

```text
request_dispatch(run) -> grant | 409 (unavailable, quota-blocked, or at capacity)
record_dispatch_delivered(run, posted_at) -> starts a pending probe window
record_quota_event(run, observed_at) -> catalog hold + run quota block count
set_availability(available_at) / clear_availability() -> shared gate
```

1. A catalog grants a dispatch only when the runs holding capacity are below
   `effective_concurrency`. A run holds capacity while it is `implementing`, or
   while it is `dispatching` with an admitted (possibly uncertain) mention
   post. A `dispatching` run that is only waiting for admission holds nothing,
   so waiting runs never block each other. A dispatching or implementing run
   whose project was disabled, edited, or lost its GitHub connection after
   enrollment can never progress, so it is moved to `blocked` with a reason and
   its active attempt fails with `PROJECT_CHANGED`; this releases its capacity.
   The project is checked before admission, so such a run never takes capacity.
   Cancel it and enroll the pull request again.
2. A quota-blocked catalog rejects dispatch until `available_at`. It never asks
   individual runs to infer a reset time. Only dispatch is gated: the scheduler
   keeps observing CI, pushes, merges, and quota replies during a hold.
3. When `available_at` passes, the next admission enters `probe`, sets
   `last_refreshed_at` to that time, limits effective concurrency to one, and
   dispatches one eligible run. The probe window starts only when that mention
   is actually delivered.
4. Once a delivered probe has run for 10 minutes without another quota event,
   the catalog returns to `normal`, restores configured concurrency, and resets
   the short-cycle failure count. This is evaluated at the next admission or
   quota observation; waiting runs become eligible on the next scheduler tick.
5. Any quota event observed at or after the end of the hold starts a new hold,
   even one from a run dispatched before the hold whose reply arrives late. This
   errs toward waiting longer; an operator can clear a hold that is too
   conservative.
6. Codex resets a usage window a fixed time (5 hours) after the window's first
   task, so an older refresh time says nothing about the next reset. Each
   delivered mention opens a new window when none is open or the previous one
   has already lasted a full window (the short cycle, or the long cycle when
   the short cycle is disabled); a recovery probe and a cleared hold always
   start a new one. A mention posted before `last_refreshed_at` (for example an
   uncertain pre-hold post found by reconciliation) belongs to the old window:
   it neither opens a window nor starts the probe window. A quota reply waits `cycle + jitter` from
   `usage_window_started_at`. If no window start is known, or the reply falls
   outside that window, the reply time is used instead: it is the latest
   possible window start, so the hold is never released early. When the short
   cycle is enabled, the first two
   consecutive failed refreshes use the short cycle; after that, the catalog
   uses the long cycle. With the short cycle disabled, every quota block uses
   the long cycle directly.
7. A reply observed before the current hold ends, or before the latest
   refresh or manual clear, is already accounted for. It increments the run's quota block count but neither
   consumes another short retry nor moves an existing hold earlier, so several
   runs hitting the same exhaustion produce one hold, and a verified reset time
   is never shortened by a late reply.
8. Disabled or unknown catalogs never silently fail over to a different model
   or account. Disabling keeps a pending hold; re-enabling restores it, and an
   expired hold resumes through a recovery probe.

The default policy is a 5-hour short cycle, a 1-week long cycle, and a 10-minute
safety jitter. These values are catalog configuration, not run-level constants.

## Manual and local refresh

**Settings → AI Catalogs** is the authoritative UI. Operators can set a
specific local reset time, clear a hold, enable/disable a catalog, and inspect
the assigned and in-use run counts. The refresh policy dialog lets them turn
the short cycle on or off and set both short-cycle hours and long-cycle days.
This allows plans such as GPT Pro, which only need the long cycle. Input is
converted to UTC; the server rejects past times.

An explicit reset time replaces the catalog's `available_at`:

- the catalog stores the new global time, even while disabled;
- every run assigned to the catalog waits on that one shared gate;
- the scheduler sees one shared gate rather than per-task timers.

Clearing a hold records a refresh at that moment: quota evidence and mentions
from before the clear are ignored, and the next delivered mention opens a new
usage window.

The optional `just sync-codex-quota` helper reads a signed-in local Codex
account and sends the verified reset to this same catalog endpoint. It must not
send credentials, raw account payloads, or a pipeline-run identifier. If it
cannot identify one blocking window, it fails closed and the UI remains the
fallback.

## Adapter boundary

Adapters report observations but do not mutate task scheduling fields.

```text
validate_catalog(catalog) -> health
dispatch(request) -> observation
reconcile(request) -> observation
classify_observation(observation) -> success | quota_limited | failed | unknown
```

The Catalog service converts `quota_limited` into a global block and task-level
block-count decision. This keeps Codex, Jules, and API-key-based adapters
behind one capacity and recovery policy.

## Rollout

1. Introduce the Catalog gateway model while preserving the seeded
   `personal-codex` binding.
2. Bind existing runs/attempts to that catalog.
3. Move dispatch admission and external-I/O rechecks behind catalog leases.
4. Move quota-event handling, task block counts, and fallback block duration
   into the Catalog service.
5. Add probe recovery and refresh/replanning.
6. Deliver the Settings AI Catalogs page.
7. Add Jules or API-key adapters only after they implement the adapter
   contract and catalog integration tests.
