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

Deferred: the connection check reports `ready` only when every check passed, so a project with no Linear connector stays `skipped` and therefore not ready.
Extracting repeated template steps into reusable workflows also remains follow-up work.

## 3. Linear Issue → Codex Implementation Dispatch

The first version advances at most one Linear issue per repository. It uses periodic tasks that acquire a short lease, perform one bounded action, persist the result, and exit. A paused run continues to occupy the repository slot until a user resumes or cancels it.

### 3.0 Execution Provider Feasibility Gate

- [ ] Against a dedicated Linear project and test repository, confirm that Codex for Linear delegation creates a Codex cloud chat, selects the intended repository/environment, follows the issue instructions, and produces a correlatable branch or draft PR.
- [ ] Decide whether Hub delegates by assigning the issue to Codex or by posting one marked `@Codex` comment. Record the required ChatGPT workspace, Codex cloud, Linear, GitHub, and repository permissions and authentication ownership.
- [ ] Identify which Linear activity, comment, chat link, branch, and PR identifiers are observable after delegation. Verify how Hub can distinguish queued, running, completed, failed, and user-blocked work without a public Codex cloud task-status API.
- [ ] Confirm that a process restart can reconcile an uncertain Linear mutation and existing Codex cloud work without delegating the issue twice.
- [ ] Keep the local Codex SDK as a separate adapter option. Adopting it would require an explicit architecture change because the current Hub boundary does not allow checking out target repositories to execute work.

Workspace Agents API is not a Codex cloud task API and is excluded from this path. Do not begin production external writes until this gate passes. If Codex for Linear cannot provide enough correlation and recovery signals, revise the adapter choice while preserving the run, attempt, lease, and idempotency contracts below.

### 3.1 Actionable Linear Issue Selection

- [x] Add a read-only Linear client that returns issue identity, project, state type, priority, timestamps, title, description (including any acceptance criteria), and blocking relations without persisting credentials or response bodies in logs.
- [x] Treat issues in completed or canceled state types as terminal. An issue is actionable when it belongs to the configured Linear project, is non-terminal, and every blocking issue is terminal.
- [x] Resume the repository's existing non-terminal `PipelineRun` before selecting new work; this depends on the durable model in 3.2.
- [x] If no run exists, choose deterministically by normalized Linear priority (urgent first and no priority last), then creation time, then issue ID.
- [x] Limit the first version to one active or paused run per `ProjectConnection`; concurrent issue execution remains a future consideration.
- [x] Cover pagination, missing descriptions, renamed workflow states, unresolved dependencies, duplicate issue results, rate limits, and disabled/edited project connections with test HTTP transports.

The selection rule uses Linear state types rather than workspace-specific state names. A canceled blocker is considered resolved for scheduling; the selected issue's own canceled state remains terminal.

### 3.2 Durable Run, Attempt, and Lease State

- [x] Add `PipelineRun` as the long-lived issue-to-PR record with `project_id`, Linear issue identity/snapshot, state, pause reason, branch, pull request identity, and optimistic revision.
- [x] Use run states `queued`, `dispatching`, `implementing`, `awaiting_ci`, `paused`, `completed`, `failed`, and `canceled`. Phase 3 stops at `awaiting_ci`; Phase 4 owns revision, merge, and completion transitions.
- [x] Add append-only `ExecutionAttempt` records with attempt number, kind (`implementation` or `revision`), request payload digest, globally unique Hub idempotency key, external correlation IDs/status when available, conversation URL, timestamps, and sanitized failure details.
- [x] Enforce one non-terminal run per project and one run per Linear issue in the database. Enforce unique `(pipeline_run_id, attempt_number)`, idempotency key, and any non-null external correlation ID constraints.
- [x] Store lease owner, token, and expiration in the database. Acquire and renew leases atomically, reject stale lease tokens on writes, and reclaim expired leases without creating a new attempt.
- [x] Validate migrations and repository behavior on PostgreSQL and keep the default SQLite tests semantically equivalent.

`ScheduleJob` remains the record for a scheduler tick. It may reference a `PipelineRun`, but it must not replace the durable run or attempt history.

Implemented on 2026-09-11: run acquisition first resumes an active or paused run, otherwise selects and records one unhandled Linear issue. Lease tokens are returned only by lease operations, and conditional database updates make acquire, renew, release, and expired-lease reclamation atomic. The migration was exercised through an SQLite upgrade/downgrade/upgrade cycle, and selection, acquisition, and lease behavior passed on both SQLite and PostgreSQL.

### 3.3 Codex Cloud Dispatch Contract

- [ ] Add per-project Codex cloud routing configuration for the expected repository/environment and the delegation method proven by the feasibility gate. Treat the Codex for Linear installation and ChatGPT workspace access as onboarding prerequisites rather than storing ChatGPT credentials in Hub.
- [ ] Persist a stable Hub correlation marker and the intended Linear mutation before delegation. Reconcile the issue's assignee, activity, and comments before retrying an uncertain mutation; reuse the same marker and never create a second delegation event for the same attempt.
- [x] Build a self-contained implementation request from an immutable Linear issue snapshot, repository, base branch, deterministic head branch, acceptance criteria, and target-repository instructions. Store its digest and redacted metadata, not connector secrets.
- [ ] Reconcile progress on later scheduler ticks through the observable Linear activity/comments and GitHub branch/PR state established by the feasibility gate. Do not keep an HTTP request open while Codex cloud runs.
- [ ] Treat GitHub as the source of implementation artifacts. Discover the correlated branch and ensure exactly one draft PR exists before moving the run to `awaiting_ci`; a Linear or Codex completion message alone is insufficient.
- [ ] Add an explicit, user-initiated execution connection check using a canary Linear issue in the test project. Never perform this external write from the existing read-only project connection check.

The dispatch adapter boundary must keep a later local Codex SDK or another execution provider possible. Linear- and Codex-specific activity details stay inside that adapter.

The provider-neutral dispatch port and deterministic Codex for Linear comment builder are implemented without sending external mutations. The live gate runbook is recorded in [`docs/codex-linear-feasibility.md`](codex-linear-feasibility.md). The comment path is the candidate because it can carry a Hub marker and explicitly name the repository; it is not enabled until the runbook proves reconciliation and environment behavior.

### 3.4 Crash Recovery and Integration Tests

- [x] Persist and commit the run, attempt, request snapshot, and idempotency key before the first external dispatch call.
- [ ] Retry an uncertain dispatch with the same Hub idempotency key and correlation marker. Reconcile Linear activity and all stored external IDs before sending another request, and never increment the attempt number solely because a process restarted.
- [ ] Locate existing work by the Linear issue and activity, Codex chat link when exposed, deterministic branch, and Hub metadata in the PR. Reuse matching resources and pause on ambiguous or conflicting matches.
- [ ] Test crashes before dispatch, after remote acceptance but before the local response is saved, after branch creation, and after PR creation. Each restart must converge on one attempt, one provider run, and one draft PR.
- [ ] Test lease expiry, two competing dispatchers, stale project revisions, Linear issue cancellation during execution, Linear/GitHub authorization failures, and sanitized external failures.

Completion criteria: Given an enabled project with GitHub and Linear connectors plus a configured Codex for Linear integration, Hub deterministically selects or resumes one actionable Linear issue, records one durable run and attempt, delegates it once, and reaches one correlated draft PR in `awaiting_ci`. Restarting Hub at every external-call boundary must converge without duplicate Codex cloud chats, delegation events, or PRs. Phase 3 does not revise, merge, close, or mark Linear issues complete.

External dependency: The initial remote path relies on [Codex for Linear](https://learn.chatgpt.com/docs/third-party/linear), which creates Codex cloud chats through issue assignment or an `@Codex` mention. The feasibility gate must establish observable recovery signals because the official [Codex cloud](https://learn.chatgpt.com/docs/cloud) documentation does not expose a general server-side task API.

## 4. CI Results → Revision, Merge, & Completion

Implement failure log relay, revision attempt limits, distinction between environment errors and code failures, pause/resume mechanisms, merge policies, and Linear completion synchronization.
Add `workflow_dispatch` support where necessary without duplicating automatic CI runs.
Invalidate prior evaluations when head or base revisions change, and re-validate GitHub criteria immediately before merging.

## 5. Events & Multi-Repository Operations

Add GitHub and Linear webhooks, routing them into the shared observation pipeline.
Handle event deduplication, out-of-order delivery, and missed events, keeping periodic polling as a recovery path.
When onboarding a second repository, evaluate whether repository-specific branching is needed in Hub.

## Future Considerations

Automatic planning/WBS generation, dynamic agent selection, concurrent issue execution, multiple internal project mappings, and custom workflow visual builders are excluded from initial completion criteria.
