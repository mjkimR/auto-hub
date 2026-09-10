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

Query actionable issues and dependencies from Linear, starting with one active issue per repository.
Introduce `PipelineRun`, execution attempts, leases, and idempotency request keys before connecting draft PR creation and Codex dispatch. Verify credentials and permissions for execution dispatch at this stage.
Add integration tests for resuming existing PRs/requests after process restarts.

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
