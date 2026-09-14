"""Read-only pull request snapshot for enrollment. Never writes to GitHub."""

import re
from typing import Any

from app.features.project_management.pipeline_runs.dispatch import CODEX_MENTION
from app.features.project_management.pipeline_runs.schemas import MAX_LINKED_ISSUES, LinkedIssue, PullRequestSnapshot
from app.features.project_management.pipelines.github import GitHubActionsReader, GitHubObservationError
from app.features.project_management.projects.services import ProjectError

# GitHub closing keywords that link an issue in the same repository.
CLOSING_REFERENCE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?):?\s+#(\d+)\b", re.IGNORECASE)
MENTION_REJECTED = "Hub posts Codex requests itself"


def linked_issue_numbers(body: str | None) -> list[int]:
    numbers: list[int] = []
    for match in CLOSING_REFERENCE.finditer(body or ""):
        number = int(match.group(1))
        if number not in numbers:
            numbers.append(number)
    return numbers


async def read_pull_request(reader: GitHubActionsReader, repository: str, number: int) -> PullRequestSnapshot:
    try:
        return await _read_pull_request(reader, repository, number)
    except GitHubObservationError as exc:
        if exc.status_code == 404:
            raise ProjectError(404, "Pull request not found in this repository") from None
        raise ProjectError(502, str(exc)) from None
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ProjectError(502, "GitHub returned incomplete pull request data") from None


async def _read_pull_request(reader: GitHubActionsReader, repository: str, number: int) -> PullRequestSnapshot:
    root = f"/repos/{repository}"
    pr = await reader._get(f"{root}/pulls/{number}")
    if pr["state"] != "open":
        raise ProjectError(422, "Only open pull requests can be enrolled")
    if str((pr["head"].get("repo") or {}).get("full_name", "")).lower() != repository:
        raise ProjectError(422, "Fork pull requests are not supported")
    title, body = pr["title"], pr.get("body")
    if CODEX_MENTION.search(f"{title}\n{body or ''}"):
        raise ProjectError(422, f"Remove @codex from the pull request title and body; {MENTION_REJECTED}")

    numbers = linked_issue_numbers(body)
    if len(numbers) > MAX_LINKED_ISSUES:
        raise ProjectError(422, f"A pull request can link at most {MAX_LINKED_ISSUES} issues")
    linked: list[LinkedIssue] = []
    for issue_number in numbers:
        issue = await _get_issue(reader, root, issue_number)
        if "pull_request" in issue:
            continue
        if CODEX_MENTION.search(f"{issue['title']}\n{issue.get('body') or ''}"):
            raise ProjectError(422, f"Remove @codex from issue #{issue_number}; {MENTION_REJECTED}")
        linked.append(
            LinkedIssue(number=issue["number"], title=issue["title"], body=issue.get("body"), url=issue["html_url"])
        )
    return PullRequestSnapshot(
        number=pr["number"],
        url=pr["html_url"],
        title=title,
        body=body,
        base_ref=pr["base"]["ref"],
        head_ref=pr["head"]["ref"],
        head_sha=pr["head"]["sha"],
        linked_issues=linked,
    )


async def _get_issue(reader: GitHubActionsReader, root: str, number: int) -> dict[str, Any]:
    try:
        return await reader._get(f"{root}/issues/{number}")
    except GitHubObservationError as exc:
        if exc.status_code == 404:
            raise ProjectError(422, f"Linked issue #{number} was not found") from None
        raise
