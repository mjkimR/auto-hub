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

## 2. Project Registration & CI Onboarding

Introduce `ProjectConnection` model, migrations, CRUD, and UI, migrating existing observation payloads.
Validate repo/project mapping uniqueness, connector types and permissions, and required job names.
Provide onboarding paths for both existing CI connection and template installation, validating one verification run during connection tests.
Templates will be distributed initially as copyable files, with repeated patterns extracted into reusable workflows later.
Provide updates that clarify selected versions and changelogs.

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
