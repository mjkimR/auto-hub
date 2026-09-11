# Codex for Linear Feasibility Gate

## Decision to Validate

Use a marked `@Codex` comment as the initial delegation candidate. The comment includes the exact GitHub repository because the official Codex for Linear documentation says this pins the repository suggestion. It also carries a unique Hub correlation marker. Assignment remains a fallback if live testing shows that comments cannot be reconciled reliably.

Hub must not assume that it can select a Codex cloud environment directly. Codex chooses an environment from the repository suggestion and its configured repo map. Hub must also treat Linear activity and the chat URL as observations rather than a complete task-status API.

Official references:

- [Use Codex in Linear](https://learn.chatgpt.com/docs/third-party/linear)
- [Codex cloud](https://learn.chatgpt.com/docs/cloud)

## Required Test Setup

- A paid ChatGPT workspace with Codex cloud chats enabled.
- Codex for Linear enabled for the workspace and linked to the test Linear account.
- A dedicated Linear project and canary issue that can be edited or discarded.
- A dedicated GitHub repository connected to Codex cloud.
- A Codex cloud environment whose first repo-map entry is the dedicated repository and whose setup can run that repository's checks.
- Linear API credentials that can read issue activities and comments and create the canary comment.

Do not use a production issue or repository for this gate.

## Canary Request

The canary should ask for a harmless, uniquely identifiable change with an objective test, such as adding one text fixture and a focused assertion. Hub first persists the `PipelineRun`, `ExecutionAttempt`, immutable request snapshot, digest, idempotency key, and a marker in this form:

```text
hub-attempt:<uuid>
```

The proposed Linear comment is deterministic:

```text
@Codex implement this issue in owner/repository.
Use `main` as the base and `codex/issue-id` as the working branch.
Follow the repository instructions and run its required checks.
Correlation: `hub-attempt:<uuid>`
```

## Evidence to Capture

Record these values without storing credentials or complete upstream response bodies:

| Boundary | Required evidence |
| --- | --- |
| Before mutation | Hub run ID, attempt ID, request digest, idempotency key, marker |
| Linear acceptance | Comment/activity ID, author or agent identity, creation timestamp |
| Codex start | Observable activity status and chat URL, if exposed |
| Repository selection | Repository and environment shown by the Codex chat |
| GitHub output | Branch, commit SHA, draft PR number and URL |
| Completion | Final Linear activity/comment and whether the chat can create or link a PR |

## Recovery Checks

Run each check with the same persisted marker and attempt:

1. Reconcile before posting and confirm no matching Linear activity exists.
2. Post once, discard the local HTTP response, then reconcile by marker and issue activity. A retry must find the first mutation rather than post again.
3. Restart Hub after Codex starts. Confirm the same chat URL and branch can be recovered.
4. Restart after branch creation and after PR creation. Confirm Hub converges on one attempt, one branch, and one draft PR.
5. Repeat with an intentionally ambiguous repo map. Confirm the run pauses instead of accepting output from the wrong repository.

## Pass Criteria

The comment path passes only if Hub can recover a unique Linear mutation, observe a stable chat link or equivalent correlation, verify the selected repository, and locate exactly one matching branch or draft PR after every simulated restart. If any identifier is unavailable or ambiguous, keep external dispatch disabled and evaluate assignment or a different execution provider.
