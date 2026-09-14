# Implementation Plan

## 1. CI Connection & Read-Only Observation — Completed

- [x] Organize README, responsibility boundaries, CI contract, and development docs.
- [x] Provide installable starter CI templates for Python+uv and Node+npm.
- [x] Validate repo ↔ Linear project connection payload and workflow/job prerequisites.
- [x] GitHub PR, workflow run, and job inspection with shared evaluation logic.
- [x] Immediate observation API, scheduled task, and latest observation query API.
- [x] Tests for earlier SHAs, missing/skipped checks, mismatched PRs/workflows, re-runs, and API failures.
- [x] Verification via `just lint`, `just check`, and `just test`.

Completion criteria: Without external service writes, evaluate required checks corresponding to current changes on specified PRs, providing reasons and GitHub run links through the API.
GitHub responses at this stage are verified using test HTTP transports and real test databases.
Live account connections and Actions execution inside target repositories will be tracked separately.

Verification on 2026-09-10: All 207 backend tests passing (including 42 new observation tests), linting, Python type checks, and Frontend build passing, generated API client refreshed.
Template YAML parsing, job names, and local document links verified.
Live GitHub API queries and Actions execution in target repositories were not performed.

## 2. Project Registration & CI Onboarding — Completed

- [x] `ProjectConnection` model, migration, and CRUD API with a revision guard on every edit.
- [x] Repo ↔ Linear project mapping uniqueness, connector provider/enabled validation, and the required-job contract.
- [x] `pipeline.observe_project` task that resolves the saved connection at run time instead of copying it into the payload.
- [x] Explicit, transactional import of legacy `pipeline.observe` schedules, preserving trigger, PRs, enabled state, and history.
- [x] Connection check that reads GitHub repository/workflow access, verifies one current PR run, and optionally confirms Linear project access.
- [x] Versioned starter templates served with their changelog and required job names, plus a project management UI.
- [x] Tests for mapping conflicts, connector misuse, revision conflicts, deletion guards, check failures, import conflicts, and scheduled runs.
- [x] Verification via `just lint`, `just check`, and `just test`.

Completion criteria: Register a repository and Linear project as one saved connection, confirm through a connection check that CI is readable and one PR verifies, and schedule observations that follow later edits to that connection without external service writes.
Connection checks record their result on the project; an edit clears it so a stale check never reads as current.
A schedule's observation is discarded if the project revision, the schedule, or its payload changed while the observation was running.

Verification on 2026-09-10: All 260 backend tests passing (including 53 new project registration and onboarding tests), linting, Python type checks, and Frontend build passing, generated API client refreshed.
Migration upgrade and downgrade were applied against a scratch SQLite database with a seeded project and adopted schedule; the downgrade restored the inline legacy payload before dropping the table.
Live GitHub and Linear API calls were not performed; both boundaries are covered with test HTTP transports.


Extracting repeated template steps into reusable workflows remains follow-up work.

The Linear mapping, connector, and access check delivered in this phase were removed by §3.0. That also resolved the earlier deferral: the connection check no longer has an optional `skipped` item, so a healthy project reports `ready`.

## 3. User PR → Codex Mention Implementation

The user opens a PR that carries the task specification and enrolls it in Hub. Hub posts a self-contained `@codex` mention on that PR, Codex cloud pushes the implementation to the PR branch, and Hub moves the run to `awaiting_ci` once the head changes. The protocol is specified in [Codex PR Mention Protocol](codex-pr-mention.md).

The first version advances at most one PR per repository. It uses periodic tasks that acquire a short lease, perform one bounded action, persist the result, and exit. A paused run continues to occupy the repository slot until a user resumes or cancels it.

### 3.0 Direction Change: Remove Linear

Decided on 2026-09-14. Hub has its own UI and durable run state, so an external tracker would only add a second source of truth to synchronize. The earlier Codex for Linear path also could not meet the phase goal: it does not create pull requests automatically, and repository, environment, and branch choice stay with Codex rather than Hub. The PR mention path was already proven end to end in `g-sandbox` (D-013, D-017).

Removed with this change: actionable Linear issue selection (formerly §3.1, implemented 2026-09-11), the Codex for Linear comment builder, and the Codex for Linear feasibility runbook. Kept: the run, attempt, lease, idempotency, and request-digest contracts from §3.2.

- [x] Remove `linear_project_id` and `linear_connector_id` from `ProjectConnection`, its schemas, the observation config, and the project UI.
- [x] Remove the `linear` connector provider. The migration deletes existing Linear connectors.
- [x] Remove the Linear client, the actionable-issue and run-acquisition endpoints, the Linear connection-check item, and their tests.
- [x] Replace the Linear-keyed columns on `pipeline_runs` (§3.2) with a forward migration that deletes the Linear-based runs and their attempts. They came from development databases only because no external dispatch was ever enabled.
- [x] Strip the removed mapping field from legacy `pipeline.observe` payloads and stored observation reports.
- [x] Regenerate the UI API client and update the README, CI contract, and templates guide.

Implemented on 2026-09-14 together with §3.1, the PR re-keying in §3.2, and request rendering in §3.3. All 289 backend tests passed on SQLite, along with Python type checks, frontend lint, and the frontend build. Migration `e6f7a8b9c0d1` was exercised on a scratch SQLite database seeded with a Linear connector, a mapped project, a legacy schedule, a stored report, and a run with an attempt, through an upgrade/downgrade/upgrade cycle. The upgrade removed the Linear connector, run, attempt, and every stored mapping field while keeping CHECK constraints and both partial unique indexes; the downgrade restored the previous schema with placeholder mapping IDs. PostgreSQL migration and test runs were not performed.

### 3.1 PR Enrollment

- [x] Add `POST /api/v1/projects/{project_id}/runs` and an Enroll PR action in the project UI that register an open PR of the project's repository as a `queued` run. Hub never selects work on its own.
- [x] Reject closed PRs, fork PRs, `@codex` in the PR title, PR body, or a linked issue, missing linked issues, and projects that already have an active run (before any GitHub read).
- [x] Record the connector's authenticated GitHub login as `github_login` in the connection check, and fail the identity item when the token does not act as a user account.
- [x] Show the onboarding checklist from the protocol (§1): Codex environment, agent internet access, environment `GH_TOKEN`, connector permissions, and repository `AGENTS.md` in the project settings dialog.
- [x] Cover open, closed, fork, mention, missing-issue, duplicate, disabled, and edited-project enrollment with test HTTP transports.

### 3.2 Durable Run, Attempt, and Lease State

- [x] Add `PipelineRun` as the long-lived record with `project_id`, work item identity/snapshot, state, pause reason, branch, pull request identity, and optimistic revision.
- [x] Use run states `queued`, `dispatching`, `implementing`, `awaiting_ci`, `paused`, `completed`, `failed`, and `canceled`. Phase 3 stops at `awaiting_ci`; Phase 4 owns revision, merge, and completion transitions.
- [x] Add append-only `ExecutionAttempt` records with attempt number, kind (`implementation` or `revision`), request payload digest, globally unique Hub idempotency key, external correlation IDs/status when available, conversation URL, timestamps, and sanitized failure details.
- [x] Enforce one non-terminal run per project in the database. Enforce unique `(pipeline_run_id, attempt_number)`, idempotency key, and any non-null external correlation ID constraints.
- [x] Store lease owner, token, and expiration in the database. Acquire and renew leases atomically, reject stale lease tokens on writes, and reclaim expired leases without creating a new attempt.
- [x] Validate migrations and repository behavior on PostgreSQL and keep the default SQLite tests semantically equivalent.
- [x] Key runs by pull request: make `pull_number` and `pull_url` required, store the PR snapshot (URL, title, body, base ref, head ref, head SHA at enrollment, linked issues), and enforce one non-terminal run per `(project_id, pull_number)`.
- [x] Use the PR head ref as `branch` instead of a Hub-generated `codex/<issue>` name.
- [x] Add delivery records under an attempt: delivery number, cause (`initial`, `silent`, `quota`, `resume`), comment ID, posted time. Enforce unique `(attempt_id, delivery_number)` and a unique non-null comment ID.

`ScheduleJob` remains the record for a scheduler tick. It may reference a `PipelineRun`, but it must not replace the durable run or attempt history.

Implemented on 2026-09-11 against Linear issues: run acquisition first resumed an active or paused run, otherwise selected and recorded one unhandled Linear issue. Lease tokens are returned only by lease operations, and conditional database updates make acquire, renew, release, and expired-lease reclamation atomic. The migration was exercised through an SQLite upgrade/downgrade/upgrade cycle, and acquisition and lease behavior passed on both SQLite and PostgreSQL. The Linear-specific parts were removed by §3.0.

### 3.3 Codex PR Mention Dispatch

- [x] Persist and commit an immutable request snapshot, canonical digest, and idempotency key under the run lease before any external call.
- [x] Build the request (version 2) from the PR snapshot, and render the mention comment in the protocol format: leading `@codex`, self-contained task with linked issues, push block for the PR head ref, trailing `hub-attempt` marker. HTML comments in the task text are removed so hidden text cannot forge a marker.
- [x] Post initial mentions only with the project's GitHub user PAT. Never post Hub comments that contain `@codex` outside task requests.
- [x] Reconcile before the initial post by listing bounded PR comments for a marker with the same attempt ID and delivery number authored by the connector's login. Adopt a found comment instead of posting again.
- [x] Move `dispatching` → `implementing` once the delivery comment is confirmed, and `implementing` → `awaiting_ci` once the PR head differs from the delivery marker's `head`. A Codex reply alone never completes the attempt.
- [x] Record Codex connector replies after a delivery, and classify usage-limit replies in one matcher.
- [x] Implement the watchdog: one silent retry after 2 h without a head change; quota retries wait 5 h 10 min and block after two retries for a user-initiated resume. Hub does not infer weekly reset timing.
- [x] Keep the adapter boundary so `openai/codex-action` can replace mention delivery without changing runs, attempts, or deliveries.

### 3.4 Remaining Validation Only: Canary, Crash Recovery, and Integration Tests

- [ ] Add a user-initiated execution canary for a dedicated test repository and PR, following the protocol (§8). Never perform this write from the read-only connection check.
- [ ] Test crashes before posting, after posting but before the local response is saved, and after the push. Each restart must converge on one attempt, one delivery, and `awaiting_ci` on the pushed head.
- [ ] Test marker spoofing by other authors, a PR closed or force-pushed during execution, a user push during `implementing`, lease expiry, two competing dispatchers, stale project revisions, GitHub authorization failures, and sanitized external failures.
- [ ] Test watchdog boundaries with a controllable clock, including tolerance edges and resume.

Completion criteria: Given an enabled project whose Codex environment meets the prerequisites, the user enrolls one open PR and Hub records one durable run and attempt, posts one mention, and reaches `awaiting_ci` on the head Codex pushed. Restarting Hub at every external-call boundary must converge without duplicate mentions. An unresponsive or quota-limited Codex ends in a paused run after bounded retries. Phase 3 does not request fixes or merge.

Implementation verification on 2026-09-14: delivery/reply persistence, retry epochs, bounded and redacted CI log excerpts, CI-fix/conflict-fix dispatch, and merge transitions are implemented. `just lint`, `just check`, and `just test` passed; 310 backend tests passed. The only unchecked work in this phase is the user-authorized live canary and the remaining crash, concurrency, and timing test coverage above.

External dependency: [Codex GitHub integration](https://learn.chatgpt.com/docs/third-party/github) documents non-review `@codex` PR comments as starting a cloud chat with the PR as context. The user-PAT identity requirement, self-push through the environment `GH_TOKEN`, and the connector reply account are observed in `g-sandbox`, not documented, and the canary must re-confirm them.

## 4. CI Results → Fix, Merge, & Completion — Implementation Complete

- [x] On red CI for the current head, post a `ci-fix` mention with failing job names and bounded log excerpts. Cap at 2 attempts per epoch, then pause.
- [x] On base conflicts, post a `conflict-fix` mention that merges the base branch. Cap at 1 attempt per epoch, then pause.
- [x] Watch every fix request with the Phase 3 watchdog.
- [x] Resume from the Hub UI starts a new epoch: fix-loop counters reset, while enrollment and implementation history persist.
- [x] Distinguish environment errors from code failures where the verification result allows it, and pause instead of requesting a code fix for environment errors.
- [x] Merge only when the latest head and base, required checks, and branch rules are re-verified immediately before merging. Mark the run `completed` from GitHub's actual merge state; closing keywords in the PR close referenced issues.
- [x] Mark a run `canceled` when its PR is closed without merging.

Invalidate prior evaluations when head or base revisions change.
Add `workflow_dispatch` support where necessary without duplicating automatic CI runs.
An LLM review lane (for example `@codex review` or a separate reviewer) is not part of the initial gate and would be added as a bounded review → fix → re-verify loop.

## 5. Events & Multi-Repository Operations

- [x] Add an HMAC-SHA256 verified GitHub webhook endpoint. It is intentionally outside API-key authentication, rejects delivery while `GITHUB_WEBHOOK_SECRET` is unset, and records only a payload digest rather than the payload body.
- [x] Deduplicate by `X-GitHub-Delivery`, route matching active-project events into the shared run advancement path, and retain polling as recovery when background processing fails.
- [ ] Configure a deployed HTTPS endpoint and subscribe a GitHub repository to `pull_request`, `issue_comment`, and `workflow_run`; verify GitHub's ping and a real event delivery.
- [ ] Test out-of-order events and missed-event recovery against a deployed repository. The local interface tests cover signature validation and duplicate deliveries.
- [ ] When onboarding a second repository, evaluate whether repository-specific branching is needed in Hub.

Implementation verification on 2026-09-14: webhook signature validation and delivery deduplication are covered with test HTTP requests. Migration `d0e1f2a3b4c5` was exercised through SQLite upgrade/downgrade/upgrade. GitHub repository configuration and live delivery remain deployment validation.

## 6. Parallel PR Execution

The original one-active-run-per-project restriction is replaced by one-active-run-per-PR. Different PRs in the same repository may progress concurrently; the same PR still has one durable run and one lease holder.

- [x] Drop the active-project uniqueness constraint while retaining the partial active `(project_id, pull_number)` uniqueness constraint.
- [x] Enroll and dispatch active runs per project in bounded parallel batches, respecting the existing global scheduler concurrency limit.
- [x] Route webhook events to the active run for the payload's PR instead of an arbitrary run for the repository.
- [ ] Test simultaneous enrollment and dispatch of separate PRs, duplicate enrollment of one PR, lease contention, and webhook routing.

## Future Considerations

The following are excluded from the initial completion criteria:

- Automatic planning/WBS generation and dynamic agent selection.
- Multiple internal project mappings and custom workflow visual builders.
- Codex quota handling beyond the current bounded retries: expose the latest trusted quota reply and retry history in the UI, add configurable per-account/repository dispatch limits, and offer a user-confirmed resume workflow. Hub must continue to avoid guessing Codex's rolling-window reset time.
