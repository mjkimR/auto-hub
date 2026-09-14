# Codex PR Mention Protocol

Hub starts Codex cloud work by posting an `@codex` comment on a pull request the user opened and enrolled. This document is the contract for that adapter. Enrollment (§2), the connection check's identity item (§1), comment rendering (§3), initial posting and marker reconciliation (§4), reply recording, watchdog handling, and head-change observation (§5) are implemented. The user-initiated live canary remains required before enabling this path for a real repository (see §8).

The protocol follows the path that completed unattended implementation and CI runs in `g-sandbox` (decisions D-013 and D-017, `gsdev pr` gate). Behaviors marked *observed* come from that operation, not from official documentation, and must be re-checked by the canary in §8.

Official references:

- [Codex GitHub integration](https://learn.chatgpt.com/docs/third-party/github): a non-`review` `@codex` PR comment "starts a cloud chat with the pull request as context and can push a fix back to the branch when it has permission to do so."
- [Codex cloud](https://learn.chatgpt.com/docs/cloud): no server-side task API is documented.

## 1. Prerequisites

These are onboarding steps. Hub cannot read Codex settings, so it records them as a checklist and proves them only through the canary.

| Where | Requirement |
| --- | --- |
| ChatGPT | Codex cloud enabled; GitHub connected with access to the repository |
| Codex environment | An environment for the repository whose setup can run the repository's checks |
| Codex environment | Agent internet access allowing `github.com` |
| Codex environment | Variable `GH_TOKEN`: fine-grained PAT limited to the repository with Contents (read/write) and Pull requests (read/write) |
| Hub GitHub connector | PAT of the **same GitHub user that is linked to Codex**, with Pull requests (read/write), Issues (read), Actions (read), and Contents (read/write) for dispatch, CI-fix, and merge automation. |
| Repository | `AGENTS.md` with conventions and the check command Codex should run |

*Observed:* mentions posted by `GITHUB_TOKEN` get no Codex response, and pushes by bot identities do not trigger `pull_request` workflows. Hub must never post mentions with an Actions or GitHub App token.

The read-only connection check records the connector's authenticated login (`GET /user`) as `github_login` so the user can confirm it is the Codex-linked account. The identity item fails when the token does not act as a user account. The check never posts a comment.

## 2. Enrollment and Task Specification

- The user opens the PR from a branch in the same repository and enrolls it explicitly with `POST /api/v1/projects/{project_id}/runs` or the Enroll PR action in the UI. Hub never selects work on its own.
- The task specification is the PR title and body, plus the title and body of each issue the PR closes with a closing keyword (`Closes #N`, up to 10). References that resolve to pull requests are ignored.
- Enrollment reads GitHub only and stores an immutable snapshot on the run: PR number, URL, title, body, base ref, head ref, head SHA, and linked issues. The run's branch is the PR head ref. Preparing an attempt builds the request from this snapshot and stores its canonical digest.
- Enrollment is rejected when the project already has an active run, the PR is closed or comes from a fork, a linked issue is missing, or `@codex` appears in the PR title, PR body, or a linked issue. *Observed:* a trigger string in a PR body can start an extra task.

## 3. Mention Comment Format

Every task comment is one top-level PR comment (`POST /repos/{owner}/{repo}/issues/{number}/comments`). It is never a reply in a review thread, because replies to Codex review comments start new tasks.

```text
@codex Implement the task below on this pull request's branch (`<head-ref>`).

## <PR title>

<PR body>

### Linked issue #<n>: <issue title>

<issue body>

## Ground rules
- Follow the repository's AGENTS.md.
- Stay within the task scope; leave unrelated code untouched.
- Run the repository's required checks and make sure they pass before you push.

Your environment provides network access to github.com and a `GH_TOKEN` environment variable
with push rights to this repository. When your work is done, push your commit to this branch yourself:

    git push "https://x-access-token:${GH_TOKEN}@github.com/<owner>/<repo>.git" HEAD:<head-ref>

After pushing, verify with `git ls-remote` that the remote branch tip equals your commit. Do not create another branch or pull request.

<!-- hub-attempt:<idempotency-key> kind=<kind> delivery=<n> head=<head-sha> -->
```

Rules:

- The comment starts with `@codex`; the marker comes last. *Observed:* only a leading mention was verified.
- Each mention runs in a fresh sandbox, so the comment must be self-contained: fix requests carry the failing check names, log excerpts, or conflict instructions in full.
- Hub's own template text never uses the word `review`, and no task line starts with it, because `@codex review` selects the separate review mode.
- HTML comments are removed from the PR and issue text before rendering, so hidden template hints or forged markers never reach the comment; an unterminated `<!--` is escaped. Rendering refuses task text that mentions Codex.
- Any Hub comment that is not a task request (status notes, pause notices) must not contain `@codex`.
- Marker values are whitespace-free tokens. The marker starts with the attempt's `hub-attempt:<idempotency-key>` correlation marker. `kind` is `implementation`, `ci-fix`, or `conflict-fix`. `head` is the PR head SHA the request was prepared against.

## 4. Posting and Reconciliation

A delivery is one posted mention for an attempt. Hub stores deliveries under the attempt with their number, cause (`initial`, `silent`, `quota`, `resume`), comment ID, and posting time.

1. Under the run lease, commit the attempt and a planned delivery before any GitHub write.
2. Reconcile: list the PR's issue comments (bounded pagination) and look for a marker with the same correlation marker and `delivery`, authored by the connector's login.
3. If found, adopt its comment ID and timestamp. If not, post the comment.
4. If the post result is uncertain (timeout, 5xx, crash before commit), do not post again in the same tick. The next tick repeats step 2.
5. A restart never creates a new attempt or delivery number; only the watchdog in §6 does.

Markers are trusted only when the comment author is the connector's login. Markers in anyone else's comments are ignored.

## 5. Progress Signals

| Signal | Source | Meaning |
| --- | --- | --- |
| Delivery comment exists | PR comments with a trusted marker | Request delivered (`implementing`) |
| Codex reply | Comments by the Codex connector account after the delivery (*observed* login `chatgpt-codex-connector`) | Acknowledgement, failure notice, or usage-limit notice; informational except usage limits |
| Head moved | PR head SHA differs from the delivery marker's `head` (for the first delivery, the enrollment snapshot's head) | Implementation or fix pushed (`awaiting_ci`) |
| CI result for the new head | Existing verification observer | Input to the Phase 4 gate |

A Codex reply without a head change is never treated as completion.
Hub cannot attribute a push to Codex. If the user pushes to the branch while a request is open, Hub treats that head as the result and evaluates CI for it; the UI shows the run as `implementing` so the user knows not to push.

Usage limits are recognized by the Codex account's reply mentioning the Codex usage settings page or stating that a Codex usage/rate limit was reached. *Observed wording*; keep the matcher in one place.

## 6. Watchdog

All delays include a five-minute tolerance for scheduler jitter. Timers reset for each new delivery.

| Condition | Action |
| --- | --- |
| No head change 2 h after the latest delivery or Codex reply, no silent retry yet | Post delivery `n+1` with cause `silent` |
| No head change 2 h after a silent retry | Pause the run: `codex-unresponsive` |
| Usage-limit reply, fewer than two quota retries | Post the next delivery 5 h 10 min after the reply |
| Usage-limit reply after two quota retries | Block the run: `codex-quota-persistent`; a user must resume it |
| User resumes a paused run | Post delivery with cause `resume`; fix-loop caps restart |

A silent retry can duplicate work if the first task was only slow. That is accepted because both tasks push to the same branch and Hub evaluates only the resulting head. Hub never guesses a weekly reset: a persistent quota limit is blocked for a user to resume after confirming availability.

## 7. Known Risks

- The mention identity, push behavior, reply account, and usage-limit wording are observed behaviors, not documented contracts.
- Open upstream reports: non-review PR mentions failing to resolve an environment ([openai/codex#20093](https://github.com/openai/codex/issues/20093)), mentions that sometimes do not trigger ([#13701](https://github.com/openai/codex/issues/13701)), and replies to Codex comments starting tasks ([#11442](https://github.com/openai/codex/issues/11442)).
- `@codex` on GitHub issues is not documented and is failing at the time of writing ([#42098](https://github.com/openai/codex/issues/42098)); Hub does not use it.
- Codex cloud chats use the default model; the mention cannot select a model or reasoning effort.
- Codex cloud usage shares the ChatGPT plan's rolling window with local Codex use.

If the mention path stops working, switch the adapter to `openai/codex-action` in a Hub-dispatched workflow that pushes to the same PR branch. Enrollment, attempts, deliveries, and the gate stay unchanged.

## 8. Canary

Before enabling mention dispatch for a real repository, run a user-initiated canary against a dedicated test repository and PR. It is never part of the read-only connection check.

The canary asks for a harmless, uniquely identifiable change with an objective check, such as one text fixture and a focused assertion. Record, without credentials or full response bodies:

| Boundary | Evidence |
| --- | --- |
| Before mutation | Run ID, attempt ID, request digest, idempotency key, delivery number |
| Delivery | Comment ID, author login, timestamp |
| Codex response | Reply author login, reply timestamp, task link if present |
| Push | New head SHA, commit author, whether `pull_request` CI started |

Recovery checks with the same attempt:

1. Reconcile before posting and confirm no matching marker exists.
2. Post once, discard the local response, then reconcile. The next tick must adopt the comment instead of posting again.
3. Restart Hub after posting and again after the push. The run must converge on one delivery and move to `awaiting_ci` on the pushed head.
4. Disable the environment's `GH_TOKEN` and confirm the watchdog retries once and then pauses with `codex-unresponsive`.

The mention path passes when every check converges without a duplicate delivery and the pushed head triggers the configured verification workflow.
