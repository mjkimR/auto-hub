import asyncio
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

import httpx
from app.features.pipelines.services import PipelineConfigurationError, PipelineObservationService
from app.features.projects.schemas import ActionableIssueSelection, LinearIssue, LinearIssueBlocker
from app.features.projects.services import ProjectError
from app.features.projects.usecases import ProjectUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends
from pydantic import ValidationError

LINEAR_PAGE_SIZE = 50
MAX_LINEAR_PAGES = 20
TERMINAL_STATE_TYPES = frozenset({"completed", "canceled"})

PROJECT_ISSUES_QUERY = """
query HubProjectIssues($projectId: String!, $after: String) {
  project(id: $projectId) {
    id
    issues(first: 50, after: $after, orderBy: createdAt) {
      nodes {
        id
        identifier
        title
        description
        priority
        createdAt
        updatedAt
        url
        state { type }
        inverseRelations(first: 10) {
          nodes {
            type
            issue { id identifier state { type } }
          }
          pageInfo { hasNextPage }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
""".strip()


def create_linear_client(token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url="https://api.linear.app", headers={"Authorization": token}, timeout=15)


def _priority_key(issue: LinearIssue) -> tuple[int, datetime, str]:
    normalized_priority = issue.priority if issue.priority in range(1, 5) else 5
    return normalized_priority, issue.created_at, str(issue.id)


def select_actionable_issue(
    issues: list[LinearIssue], excluded_issue_ids: set[UUID] | None = None
) -> ActionableIssueSelection:
    excluded_issue_ids = excluded_issue_ids or set()
    non_terminal = [
        issue for issue in issues if issue.state_type not in TERMINAL_STATE_TYPES and issue.id not in excluded_issue_ids
    ]
    actionable = [
        issue for issue in non_terminal if all(blocker.state_type in TERMINAL_STATE_TYPES for blocker in issue.blockers)
    ]
    actionable.sort(key=_priority_key)
    return ActionableIssueSelection(
        selected=actionable[0] if actionable else None,
        inspected_count=len(issues),
        actionable_count=len(actionable),
        blocked_count=len(non_terminal) - len(actionable),
    )


class LinearIssueReader:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def select(self, project_id: UUID, excluded_issue_ids: set[UUID] | None = None) -> ActionableIssueSelection:
        issues = await self._list_project_issues(project_id)
        return select_actionable_issue(issues, excluded_issue_ids)

    async def _list_project_issues(self, project_id: UUID) -> list[LinearIssue]:
        by_id: dict[UUID, LinearIssue] = {}
        after: str | None = None
        seen_cursors: set[str] = set()
        for _ in range(MAX_LINEAR_PAGES):
            body = await self._post(project_id, after)
            project = (body.get("data") or {}).get("project")
            if not isinstance(project, dict) or project.get("id") != str(project_id):
                raise ProjectError(422, "Linear project is not accessible with this connector")
            connection = project.get("issues")
            if not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list):
                raise ProjectError(502, "Linear returned an invalid issue list")
            for raw in connection["nodes"]:
                issue = self._parse_issue(raw)
                existing = by_id.get(issue.id)
                if existing is not None and existing != issue:
                    raise ProjectError(502, "Linear returned conflicting data for the same issue")
                by_id[issue.id] = issue
            page_info = connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                return list(by_id.values())
            cursor = page_info.get("endCursor")
            if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
                raise ProjectError(502, "Linear returned an invalid pagination cursor")
            seen_cursors.add(cursor)
            after = cursor
        raise ProjectError(422, f"Linear project exceeds the {LINEAR_PAGE_SIZE * MAX_LINEAR_PAGES}-issue safety limit")

    async def _post(self, project_id: UUID, after: str | None) -> dict[str, Any]:
        try:
            response = await self.client.post(
                "/graphql",
                json={
                    "query": PROJECT_ISSUES_QUERY,
                    "variables": {"projectId": str(project_id), "after": after},
                },
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError, AttributeError):
            raise ProjectError(502, "Could not read Linear issues") from None
        if not isinstance(body, dict):
            raise ProjectError(502, "Linear returned an invalid response")
        errors = body.get("errors")
        if errors:
            codes = {
                error.get("extensions", {}).get("code")
                for error in errors
                if isinstance(error, dict) and isinstance(error.get("extensions"), dict)
            }
            if "RATELIMITED" in codes:
                raise ProjectError(429, "Linear issue query was rate limited")
            raise ProjectError(502, "Linear could not complete the issue query")
        return body

    @staticmethod
    def _parse_issue(raw: object) -> LinearIssue:
        if not isinstance(raw, dict):
            raise ProjectError(502, "Linear returned an invalid issue")
        inverse_relations = raw.get("inverseRelations")
        if not isinstance(inverse_relations, dict) or not isinstance(inverse_relations.get("nodes"), list):
            raise ProjectError(502, "Linear returned invalid issue relations")
        if (inverse_relations.get("pageInfo") or {}).get("hasNextPage"):
            raise ProjectError(422, "An issue has too many blocking relations to evaluate safely")
        blockers: list[LinearIssueBlocker] = []
        for relation in inverse_relations["nodes"]:
            if not isinstance(relation, dict) or relation.get("type") != "blocks":
                continue
            issue = relation.get("issue") or {}
            state = issue.get("state") or {}
            try:
                blockers.append(
                    LinearIssueBlocker.model_validate(
                        {
                            "id": issue.get("id"),
                            "identifier": issue.get("identifier"),
                            "state_type": state.get("type"),
                        }
                    )
                )
            except ValidationError:
                raise ProjectError(502, "Linear returned an invalid blocking issue") from None
        state = raw.get("state") or {}
        try:
            return LinearIssue.model_validate(
                {
                    "id": raw.get("id"),
                    "identifier": raw.get("identifier"),
                    "title": raw.get("title"),
                    "description": raw.get("description"),
                    "priority": raw.get("priority"),
                    "state_type": state.get("type"),
                    "created_at": raw.get("createdAt"),
                    "updated_at": raw.get("updatedAt"),
                    "url": raw.get("url"),
                    "blockers": blockers,
                }
            )
        except ValidationError:
            raise ProjectError(502, "Linear returned an invalid issue") from None


class SelectActionableIssueUseCase:
    def __init__(
        self,
        projects: Annotated[ProjectUseCase, Depends()],
        observer: Annotated[PipelineObservationService, Depends()],
    ):
        self.projects = projects
        self.observer = observer

    async def execute(
        self, project_id: UUID, *, excluded_issue_ids: set[UUID] | None = None
    ) -> ActionableIssueSelection:
        project = await self.projects.get(project_id)
        if not project.enabled:
            raise ProjectError(422, "Project is disabled")
        if project.linear is None or project.linear.connector_id is None:
            raise ProjectError(422, "Add a Linear connection before selecting issues")
        try:
            token = await self.observer.get_token(project.linear.connector_id, "linear")
        except PipelineConfigurationError as exc:
            raise ProjectError(422, str(exc)) from None
        try:
            async with asyncio.timeout(30):
                async with create_linear_client(token) as client:
                    result = await LinearIssueReader(client).select(project.linear.project_id, excluded_issue_ids)
        except TimeoutError:
            raise ProjectError(504, "Linear issue query exceeded its time budget") from None

        async with AsyncTransaction() as session:
            current = await self.projects.service.repo.get(session, project_id)
            if (
                current is None
                or not current.enabled
                or current.revision != project.revision
                or current.linear_project_id != project.linear.project_id
                or current.linear_connector_id != project.linear.connector_id
            ):
                raise ProjectError(
                    409, "Project changed during the Linear issue query; retry with the new configuration"
                )
        return result
