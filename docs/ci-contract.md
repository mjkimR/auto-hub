# CI Connection Contract

## Current Supported Scope

Observes PRs originating from the same repository on GitHub.com and Actions workflows triggered by `pull_request` events.
Limits: 1 workflow per connection, up to 30 required jobs, and up to 10 explicitly specified PRs.
Fork PRs, manual workflow dispatches, push-only CIs, and alternative CI providers are not yet supported.
These limits represent the initial observation phase and are not constraints of the final project model.

If existing CI is present, register the workflow filename and required job names.
If there is no CI, install a [starter template](../templates/github-actions/README.md).
Hub does not parse test commands or technology stacks.

## Input

The immediate observation API endpoint is `POST /api/v1/pipelines/inspect`.
Use the following JSON structure as the request body. Replace UUIDs, repo, and PR numbers with actual values:

```json
{
  "repository": "owner/my-app",
  "linear_project_id": "11111111-1111-4111-8111-111111111111",
  "github_connector_id": "22222222-2222-4222-8222-222222222222",
  "pull_numbers": [42],
  "verification": {
    "workflow": "ci.yml",
    "required_jobs": ["lint", "test", "build"],
    "event": "pull_request"
  }
}
```

- `workflow`: The filename under `.github/workflows/`, not the workflow's display name.
- `required_jobs`: Exact job names as displayed in GitHub Actions. Cannot be empty or contain duplicates.
- `linear_project_id`: Metadata representing the 1 repo ↔ 1 project connection. Not yet validated against Linear.
- `github_connector_id`: Must reference an active `github` Connector.
- The Connector's `credentials` stores `{"token": "<GitHub token>"}`. Never place the token directly into the payload.
- GitHub fine-grained permissions required for this observation: Actions (read) and Pull requests (read) on the target repo. Permissions for automated write phases will be specified separately in future work.

The API uses existing Hub API key authentication. Authorize via `/docs` to issue requests.
Immediate observation only sends read requests to GitHub and does not persist reports in the database.

## Evaluation

1. Query PR head/base and status. Closed PRs become `closed`; fork PRs become `blocked`.
2. Find workflow runs matching the specified workflow where event, repo, PR number, and current head match.
3. Select the latest run. Previous successes never mask recent pending or failing runs.
4. Fetch latest job results page by page. Missing pages are never treated as success.
5. Re-check the run's attempt/status/conclusion/updated_at and PR head/base/state to detect mutations during observation.
6. A status of `passed` is granted only when both the workflow and all required jobs are explicitly successful.

| Status | Meaning |
| --- | --- |
| `waiting` | No run for current head, run in progress, or PR/run mutated during observation |
| `failed` | Workflow failure (code failure vs. environment failure is not yet distinguished) |
| `blocked` | Contract unfulfilled: missing job, duplicated job names, skipped, neutral, cancelled, timed out, awaiting approval, etc. |
| `passed` | Workflow and all required jobs succeeded (independent of merge approval) |
| `closed` | Closed PR (distinguishing merged vs. abandoned close is part of follow-up work) |

If an unregistered job fails and causes the overall workflow to fail, it will not pass.
During re-runs, the observer waits. If only selected failed jobs were re-run, GitHub's `filter=latest` job list is used.
If the workflow was never triggered, it is never indefinitely marked as passed.
Diagnosing missing runs, handling wait timeouts, and triggering automatic re-runs are responsibilities of the upcoming progression gate.

PR CI may checkout the merge ref synthesized by GitHub. Matching the head commit here verifies which PR revision the run is tied to, rather than a strict SHA equality check against the checked-out merge commit.
The current observer does not certify re-verification against the latest base branch updates or branch protection enforcement.
During the merge step, base branch freshness, reviews, and branch rules must be verified anew.

API errors, parsing failures, incomplete pages, and 60-second observation timeouts are never converted into `passed` or CI failures.
The immediate observation API returns 502 for upstream errors and 422 for invalid configuration payloads.
Raw response bodies and tokens are never included in error messages.

## Periodic Observation

Configure the following values in `POST /api/v1/schedule_configs` or the schedule management UI:

- `task_func`: `pipeline.observe`
- `interval_seconds`: For example `300` (mutually exclusive with `cron_expression`)
- `payload`: The connection JSON shown above
- `enabled`: `true` when active

Creating a schedule does not automatically start a timer.
Due schedules are executed when external triggers call `POST /api/v1/dispatchers/trigger`.
Because this endpoint also executes other due schedules, use `/pipelines/inspect` when testing observation in isolation.

Observation reports can be queried via `GET /api/v1/pipelines/observations/{schedule_id}`.
Returns 404 before initial observation, after schedule deletion or type change, or after payload modification prior to a new observation run.
A schedule report represents the most recent successful query result. Even if subsequent queries encounter errors, prior reports are retained; inspect both `observed_at` and `ScheduleJob` history together. Never use this as sole justification for real-time merges.
Reports are stored in the database's `TaskState` table without requiring new database migrations.

## References

- [GitHub workflow runs API](https://docs.github.com/en/rest/actions/workflow-runs)
- [GitHub workflow jobs API](https://docs.github.com/en/rest/actions/workflow-jobs)
- [PR events and merge refs](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request)
- [Reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
