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
- No Linear integration: Hub is the single source of truth for run state.

## Verification

On 2026-09-14, a live canary on `mjkimR/test-sandbox` against Cloud Run and
Aiven PostgreSQL enrolled PRs, posted one `@codex` request, received a Codex
push, observed passing Actions CI, and completed the merge.

Local verification on 2026-09-14:

- `just test`: 370 backend tests passing.
- `just test-ui`: 2 frontend component tests passing.
- `just lint` and `just check`: passing.

The automated suite covers crash recovery around mention delivery and head
changes, marker reconciliation, watchdog tolerance edges, webhook routing and
polling recovery, lease takeover, and UI enrollment/pause behavior.

## Optional follow-up canaries

These are not required for the current single-PR operating model:

- In a sandbox, enroll two PRs at once to validate production scheduler
  concurrency and duplicate enrollment handling.
- If webhook delivery reliability becomes a concern, validate a deliberately
  missed delivery recovering on the next scheduler poll.
- When onboarding a second repository, decide whether repository-specific
  branching policy is necessary.

## Explicitly deferred

- Automatic planning/WBS generation and dynamic agent selection.
- Additional catalog families, project-level catalog selection, and richer quota history. The active Codex global-availability contract is in [AI Catalog Gateway](ai-catalogs.md).
- A bounded LLM review lane before merge.
