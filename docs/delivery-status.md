# Delivery Status

Auto Hub is implemented and deployed. This document records the current
delivery state; the durable `@codex` request contract lives in
[Codex PR Mention Protocol](codex-pr-mention.md).

## Delivered

- GitHub CI observation, saved project connections, and project onboarding.
- PR enrollment, durable run/attempt/delivery history, leases, idempotency,
  mention reconciliation, watchdog retries, CI fixes, merge, and cancellation.
- HMAC-verified GitHub webhooks with delivery deduplication and polling
  recovery, plus parallel runs for different PRs in the same project.
- AI catalog gateway with per-kind quota policies (Codex usage windows, daily
  task caps), a dispatch ledger, pluggable pipeline execution adapters, and
  scheduled Jules sessions (`jules.session`, `jules.sync_sessions`). See
  [AI Catalog Gateway](ai-catalogs.md). This work is not yet committed or
  deployed as of 2026-09-15.
- No Linear integration: Hub is the single source of truth for run state. A
  `linear` connector provider exists only so the connectors UI can store one.

## Verification

On 2026-09-14, a live canary on `mjkimR/test-sandbox` against Cloud Run and
Aiven PostgreSQL enrolled PRs, posted one `@codex` request, received a Codex
push, observed passing Actions CI, and completed the merge.

Local verification on 2026-09-15 (AI catalog generalization):

- Backend: 428 tests passing on SQLite and on PostgreSQL (testcontainers).
- Migrations: the full Alembic chain upgrades, downgrades, and re-upgrades on
  PostgreSQL 16. `alembic check` reports only two pre-existing column-comment
  differences (`pipeline_runs.pull_snapshot`, `schedule_configs.next_run_at`).
- Frontend: 7 component tests, `svelte-check`, production build, and lint
  passing.
- Jules was exercised only against a mocked HTTP transport; no live Jules or
  post-refactor Codex canary has run.

The automated suite covers crash recovery around delivery and head changes,
marker reconciliation, watchdog tolerance edges, webhook routing and polling
recovery, lease takeover, catalog admission and ledger counting, Jules session
creation, rate limiting, and reconciliation, and UI enrollment, pause, and
catalog policy editing.

## Follow-up canaries

- Re-run the Codex PR canary after deploying the refactored gateway.
- Run one live Jules session: confirm the v1alpha field names, the error
  returned at the daily and concurrent caps, and whether a limit is reported
  as HTTP 429.
- In a sandbox, enroll two PRs at once to validate production scheduler
  concurrency and duplicate enrollment handling.
- If webhook delivery reliability becomes a concern, validate a deliberately
  missed delivery recovering on the next scheduler poll.
- When onboarding a second repository, decide whether repository-specific
  branching policy is necessary.

## Explicitly deferred

- Automatic planning/WBS generation and dynamic agent selection.
- Project-level catalog selection (pipeline runs always use `personal-codex`),
  Jules pull request delivery, a Jules session results UI, and richer quota
  history. Open items are tracked in the
  [AI Catalog generalization worklog](ai-catalogs-worklog-2026-09-15.md#남은-작업--알려진-제약).
- A bounded LLM review lane before merge.
