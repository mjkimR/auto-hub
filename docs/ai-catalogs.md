# AI Catalog Gateway

## Status

The seeded `personal-codex` record is the initial **AI Catalog gateway**. It
owns dispatch admission, quota block state, probe recovery, and per-run quota
block counts. The persistence table, API, run reference, and UI are all named
AI Catalog. A separate adapter/credential-binding entity remains a future
extraction once a second adapter is introduced.

## Why a catalog is the gateway

A quota is attached to an AI account and its capacity, not to a pipeline run.
Likewise, a concurrency limit is meaningful only across every task sharing the
same account/model route. If runs own their own retry timestamps they can race,
retry together after a reset, and defeat the intended safety limit.

Every AI-bound task therefore submits a dispatch request to exactly one
catalog. The catalog decides whether to dispatch now, defer it, block the task,
or refresh its schedule. Tasks do not calculate quota retry times.

```text
Pipeline run / attempt
        │ request dispatch
        ▼
AI Catalog Gateway ── adapter binding ── Codex GitHub mention / Jules / API model
  capacity leases
  global block window
  recovery probe
  deferred-task refresh
  per-task quota block count
```

## Catalog model

| Field | Responsibility |
| --- | --- |
| `id`, `key`, `name` | Stable catalog identity and operator-facing label |
| `adapter` | Execution integration selected by the catalog |
| `connector_ids` | Optional credential/connection dependencies for the adapter |
| `configured_concurrency` | Normal maximum concurrent external executions |
| `effective_concurrency` | Current maximum, reduced to `1` in recovery probe mode |
| `state` | `normal`, `quota_blocked`, `probe`, `disabled`, or `unknown` |
| `block_until` | Earliest UTC dispatch time while quota-blocked |
| `block_source`, `block_note`, `blocked_at` | Safe operator-visible evidence and audit metadata |
| `probe_started_at`, `probe_window_minutes` | Recovery observation window; initial window is 10 minutes |
| `revision` | Optimistic state/configuration revision |

Catalog state is global. A task assignment records only `catalog_id`, its
quota block count, and the catalog decision that last deferred or blocked it.
It does not own a quota-derived retry timestamp.

## Gateway decisions

The catalog service exposes these decisions to the scheduler and adapters:

```text
request_dispatch(task) -> grant | defer(until) | task_blocked(reason)
complete_dispatch(task, outcome) -> capacity release / recovery observation
record_quota_event(task, event_time) -> catalog block + task decision
refresh(block_until) -> replan deferred tasks
```

1. A normal catalog grants a capacity lease only when active leases are below
   `effective_concurrency`.
2. A quota-blocked catalog defers every non-blocked task until `block_until`.
   It never asks individual tasks to infer a reset time.
3. When `block_until` passes, the catalog enters `probe`, limits effective
   concurrency to one, and dispatches one eligible task.
4. If that probe runs for 10 minutes without another quota event, the catalog
   returns to `normal`, restores configured concurrency, and refreshes all
   deferred tasks for immediate eligibility.
5. Any quota event during probe returns the catalog to `quota_blocked` and
   starts a new block window.
6. A task that has caused two quota blocks is catalog-blocked. Its catalog
   assignment remains blocked even after the global catalog recovers; other
   tasks may proceed.
7. Disabled or unknown catalogs never silently fail over to a different model
   or account.

The existing five-hour-ten-minute value is a catalog policy fallback only when
the adapter cannot prove a reset time. It is never a run-level constant.

## Manual and local refresh

**Settings → AI Catalogs** is the authoritative UI. Operators can set a
specific local reset time, clear a hold, enable/disable a catalog, and inspect
active/deferred/blocked counts. Input is converted to UTC; the server rejects
past times.

An explicit reset time invokes `refresh(block_until)`:

- the catalog stores the new global time;
- all deferred catalog tasks are refreshed against it;
- the scheduler sees one shared gate rather than per-task timers.

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
