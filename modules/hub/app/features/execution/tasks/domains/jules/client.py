"""Jules REST API (v1alpha) client: https://developers.google.com/jules/api. It sends prompts, never repository code."""

import re
from typing import Any

import httpx

JULES_API_BASE_URL = "https://jules.googleapis.com/v1alpha/"
SESSION_NAME = re.compile(r"sessions/[A-Za-z0-9_-]+")
# Reconciliation looks only at recent sessions; an older unconfirmed create is presumed lost by the caller.
LIST_PAGE_LIMIT = 3


class JulesApiError(RuntimeError):
    """Sanitized upstream failure: no response body, credentials, or request headers."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def create_jules_client(api_key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=JULES_API_BASE_URL, headers={"X-Goog-Api-Key": api_key}, timeout=30)


class JulesClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self.client.request(method, path, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise JulesApiError(f"Jules API returned HTTP {status}", status) from None
        except httpx.RequestError:
            raise JulesApiError("Jules API request failed") from None
        try:
            value = response.json()
        except ValueError:
            raise JulesApiError("Jules API returned invalid JSON") from None
        if not isinstance(value, dict):
            raise JulesApiError("Jules API returned an unexpected payload")
        return value

    async def create_session(
        self, *, repository: str, starting_branch: str, prompt: str, title: str, auto_create_pr: bool
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "sessions",
            json={
                "prompt": prompt,
                "title": title,
                "sourceContext": {
                    "source": f"sources/github/{repository}",
                    "githubRepoContext": {"startingBranch": starting_branch},
                },
                "automationMode": "AUTO_CREATE_PR" if auto_create_pr else "AUTOMATION_MODE_UNSPECIFIED",
                "requirePlanApproval": False,
            },
        )

    async def get_session(self, name: str) -> dict[str, Any]:
        if not SESSION_NAME.fullmatch(name):
            raise JulesApiError("Jules session name is invalid")
        return await self._request("GET", name)

    async def find_session_by_title(self, title: str) -> dict[str, Any] | None:
        """Session creation has no idempotency key, so an unconfirmed create is found again by its unique title."""
        page_token: str | None = None
        for _ in range(LIST_PAGE_LIMIT):
            params: dict[str, str | int] = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token
            page = await self._request("GET", "sessions", params=params)
            for item in page.get("sessions") or []:
                if isinstance(item, dict) and item.get("title") == title:
                    return item
            page_token = page.get("nextPageToken")
            if not isinstance(page_token, str) or not page_token:
                return None
        return None
