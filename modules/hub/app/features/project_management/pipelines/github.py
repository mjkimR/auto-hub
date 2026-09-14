"""Read-only GitHub Actions adapter. Never checks out or executes repository code."""

from typing import Any
from urllib.parse import quote

import httpx
from app.features.project_management.pipelines.gate import evaluate_verification
from app.features.project_management.pipelines.schemas import (
    JobSnapshot,
    PipelineObservationConfig,
    PullObservation,
    RunSnapshot,
    VerificationResult,
    VerificationStatus,
)


class GitHubObservationError(RuntimeError):
    """Sanitized upstream failure: no response body, credentials, or request headers."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def create_github_client(token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="https://api.github.com",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=10,
        follow_redirects=False,
    )


class GitHubActionsReader:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def _get(self, path: str, params: dict[str, str | int] | None = None) -> dict[str, Any]:
        try:
            response = await self.client.get(path, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise GitHubObservationError(f"GitHub observation returned HTTP {status}", status) from None
        except httpx.RequestError:
            raise GitHubObservationError("GitHub observation request failed") from None
        try:
            value = response.json()
        except ValueError:
            raise GitHubObservationError("GitHub observation returned invalid JSON") from None
        if not isinstance(value, dict):
            raise GitHubObservationError("GitHub observation returned an invalid object")
        return value

    async def _get_list(self, path: str, params: dict[str, str | int] | None = None) -> list[dict[str, Any]]:
        try:
            response = await self.client.get(path, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GitHubObservationError(f"GitHub observation returned HTTP {exc.response.status_code}") from None
        except httpx.RequestError:
            raise GitHubObservationError("GitHub observation request failed") from None
        try:
            value = response.json()
        except ValueError:
            raise GitHubObservationError("GitHub observation returned invalid JSON") from None
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise GitHubObservationError("GitHub observation returned an invalid list")
        return value

    async def current_login(self) -> str:
        user = await self._get("/user")
        login = user.get("login")
        if not isinstance(login, str) or not login:
            raise GitHubObservationError("GitHub returned an incomplete authenticated user")
        return login

    async def reconcile_issue_comment(
        self, repository: str, pull_number: int, marker: str, author: str
    ) -> dict[str, Any] | None:
        """Find one trusted marker using a bounded list of PR issue comments."""
        for page in range(1, 11):
            comments = await self._get_list(
                f"/repos/{repository}/issues/{pull_number}/comments", {"per_page": 100, "page": page}
            )
            for comment in comments:
                if comment.get("user", {}).get("login") == author and marker in str(comment.get("body") or ""):
                    return comment
            if len(comments) < 100:
                return None
        raise GitHubObservationError("GitHub comment reconciliation exceeded its pagination limit")

    async def list_issue_comments(self, repository: str, pull_number: int) -> list[dict[str, Any]]:
        comments: list[dict[str, Any]] = []
        for page in range(1, 11):
            batch = await self._get_list(
                f"/repos/{repository}/issues/{pull_number}/comments", {"per_page": 100, "page": page}
            )
            comments.extend(batch)
            if len(batch) < 100:
                return comments
        raise GitHubObservationError("GitHub comment observation exceeded its pagination limit")

    async def post_issue_comment(self, repository: str, pull_number: int, body: str) -> dict[str, Any]:
        try:
            response = await self.client.post(f"/repos/{repository}/issues/{pull_number}/comments", json={"body": body})
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise GitHubObservationError(f"GitHub mention delivery returned HTTP {status}", status) from None
        except httpx.RequestError:
            raise GitHubObservationError("GitHub mention delivery request failed") from None
        try:
            value = response.json()
        except ValueError:
            raise GitHubObservationError("GitHub mention delivery returned invalid JSON") from None
        if not isinstance(value, dict):
            raise GitHubObservationError("GitHub mention delivery returned an invalid object")
        return value

    async def find_pull_request(self, repository: str, head_branch: str) -> dict[str, Any] | None:
        owner = repository.split("/")[0]
        pulls = await self._get_list(f"/repos/{repository}/pulls", {"head": f"{owner}:{head_branch}", "state": "open"})
        if not pulls:
            pulls = await self._get_list(f"/repos/{repository}/pulls", {"head": head_branch, "state": "open"})
        return pulls[0] if pulls else None

    async def _list(self, path: str, key: str, params: dict[str, str | int]) -> list[dict[str, Any]]:
        items = []
        # Bounded pagination: incomplete observations fail instead of passing with partial evidence.
        for page in range(1, 11):
            data = await self._get(path, {**params, "per_page": 100, "page": page})
            batch = data.get(key)
            if not isinstance(batch, list) or any(not isinstance(item, dict) for item in batch):
                raise GitHubObservationError("GitHub observation returned an invalid list")
            items.extend(batch)
            if len(batch) < 100:
                total = data.get("total_count")
                if isinstance(total, int) and total > len(items):
                    raise GitHubObservationError("GitHub observation returned an incomplete page")
                return items
        raise GitHubObservationError("GitHub observation exceeded its pagination limit")

    async def observe_pull(self, config: PipelineObservationConfig, number: int) -> PullObservation:
        try:
            return await self._observe_pull(config, number)
        except (AttributeError, KeyError, TypeError, ValueError):
            raise GitHubObservationError("GitHub observation returned incomplete data") from None

    async def _observe_pull(self, config: PipelineObservationConfig, number: int) -> PullObservation:
        root = f"/repos/{config.repository}"
        pr_path = f"{root}/pulls/{number}"
        pr = await self._get(pr_path)
        head_sha = pr["head"]["sha"]
        observation = PullObservation(
            number=number,
            head_sha=head_sha,
            base_sha=pr["base"]["sha"],
            url=pr["html_url"],
            result=VerificationResult(status=VerificationStatus.WAITING, reason="Awaiting verification"),
        )
        if pr["state"] != "open":
            observation.result = VerificationResult(status=VerificationStatus.CLOSED, reason="PR is closed")
            return observation
        head_repo = (pr["head"].get("repo") or {}).get("full_name", "")
        if head_repo.lower() != config.repository.lower():
            observation.result = VerificationResult(
                status=VerificationStatus.BLOCKED, reason="Fork PRs are not supported in the initial observer"
            )
            return observation

        workflow = quote(config.verification.workflow, safe="")
        runs = await self._list(
            f"{root}/actions/workflows/{workflow}/runs",
            "workflow_runs",
            {"head_sha": head_sha, "event": config.verification.event},
        )
        candidates = [
            run
            for run in runs
            if run["head_sha"] == head_sha
            and run["event"] == config.verification.event
            and run["path"] == f".github/workflows/{config.verification.workflow}"
            and (run.get("head_repository") or {}).get("full_name", "").lower() == config.repository.lower()
            and any(
                pull["number"] == number and pull["head"]["sha"] == head_sha for pull in run.get("pull_requests", [])
            )
        ]
        if candidates:
            # Select the latest execution, never an older successful run while its replacement is pending.
            run = max(candidates, key=lambda item: (item["run_number"], item["id"]))
            jobs = await self._list(f"{root}/actions/runs/{run['id']}/jobs", "jobs", {"filter": "latest"})
            observation.run = RunSnapshot(
                id=run["id"],
                attempt=run["run_attempt"],
                head_sha=run["head_sha"],
                status=run["status"],
                conclusion=run["conclusion"],
                url=run["html_url"],
                jobs=[
                    JobSnapshot(
                        name=job["name"], status=job["status"], conclusion=job["conclusion"], url=job.get("html_url")
                    )
                    for job in jobs
                ],
            )
            latest = await self._get(f"{root}/actions/runs/{run['id']}")
            if any(latest[key] != run[key] for key in ("run_attempt", "status", "conclusion", "updated_at")):
                observation.result = VerificationResult(
                    status=VerificationStatus.WAITING, reason="Workflow changed during observation; inspect again"
                )
                return observation

        current_pr = await self._get(pr_path)
        if (
            current_pr["head"]["sha"] != head_sha
            or current_pr["base"]["sha"] != pr["base"]["sha"]
            or current_pr["state"] != pr["state"]
        ):
            observation.result = VerificationResult(
                status=VerificationStatus.WAITING, reason="PR changed during observation; inspect again"
            )
            return observation
        observation.result = evaluate_verification(config.verification, head_sha, observation.run)
        return observation
