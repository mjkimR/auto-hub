import asyncio
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import httpx
from app.features.pipelines import services as pipeline_services
from app.features.pipelines.github import GitHubActionsReader, GitHubObservationError
from app.features.pipelines.services import PipelineConfigurationError, PipelineObservationService
from app.features.projects.schemas import ConnectionCheck, ConnectionCheckItem
from app.features.projects.services import ProjectError
from app.features.projects.usecases import ProjectUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends


def create_linear_client(token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url="https://api.linear.app", headers={"Authorization": token}, timeout=10)


async def check_linear_project(token: str, project_id: UUID) -> None:
    try:
        async with create_linear_client(token) as client:
            response = await client.post(
                "/graphql",
                json={
                    "query": "query HubProject($id: String!) { project(id: $id) { id } }",
                    "variables": {"id": str(project_id)},
                },
            )
            response.raise_for_status()
            body = response.json()
            if body.get("errors") or ((body.get("data") or {}).get("project") or {}).get("id") != str(project_id):
                raise ProjectError(422, "Linear project is not accessible with this connector")
    except (httpx.HTTPError, ValueError, AttributeError):
        raise ProjectError(422, "Could not read the Linear project; check the API key and project access") from None


class CheckProjectUseCase:
    def __init__(
        self, projects: Annotated[ProjectUseCase, Depends()], observer: Annotated[PipelineObservationService, Depends()]
    ):
        self.projects = projects
        self.observer = observer

    async def execute(self, project_id: UUID, pull_number: int) -> ConnectionCheck:
        project = await self.projects.get(project_id)
        checks: list[ConnectionCheckItem] = []
        observation = None
        try:
            async with asyncio.timeout(75):
                try:
                    if project.github is None:
                        raise ProjectError(422, "Add a GitHub connection before checking CI")
                    token = await self.observer.get_token(project.github.github_connector_id, "github")
                    async with pipeline_services.create_github_client(token) as client:
                        reader = GitHubActionsReader(client)
                        repository = await reader._get(f"/repos/{project.github.repository}")
                        workflow = await reader._get(
                            f"/repos/{project.github.repository}/actions/workflows/{project.github.verification.workflow}"
                        )
                        if repository.get("full_name", "").lower() != project.github.repository or repository.get(
                            "archived"
                        ):
                            raise ProjectError(422, "Repository is archived or does not match this connection")
                        if (
                            workflow.get("state") != "active"
                            or workflow.get("path") != f".github/workflows/{project.github.verification.workflow}"
                        ):
                            raise ProjectError(422, "Configured workflow is missing, disabled, or has a different path")
                    checks.append(
                        ConnectionCheckItem(
                            name="GitHub access", status="passed", detail="Repository and active workflow are readable"
                        )
                    )
                    observation = await self.observer.observe(project.observation_config([pull_number]))
                    result = observation.pulls[0].result
                    checks.append(
                        ConnectionCheckItem(
                            name="PR verification",
                            status="passed" if result.status == "passed" else "failed",
                            detail=result.reason,
                        )
                    )
                except (GitHubObservationError, PipelineConfigurationError, ProjectError) as exc:
                    checks.append(ConnectionCheckItem(name="GitHub / CI", status="failed", detail=str(exc)))
                if project.linear and project.linear.connector_id:
                    try:
                        token = await self.observer.get_token(project.linear.connector_id, "linear")
                        await check_linear_project(token, project.linear.project_id)
                        checks.append(
                            ConnectionCheckItem(
                                name="Linear access", status="passed", detail="Configured project is readable"
                            )
                        )
                    except (PipelineConfigurationError, ProjectError) as exc:
                        checks.append(ConnectionCheckItem(name="Linear access", status="failed", detail=str(exc)))
                else:
                    checks.append(
                        ConnectionCheckItem(
                            name="Linear access",
                            status="skipped",
                            detail="Select a Linear connector to validate project access",
                        )
                    )
        except TimeoutError:
            checks.append(
                ConnectionCheckItem(
                    name="Connection check", status="failed", detail="Connection check exceeded its time budget"
                )
            )
        has_passed = any(check.status == "passed" for check in checks)
        has_failed = any(check.status == "failed" for check in checks)
        report = ConnectionCheck(
            checked_at=datetime.now(UTC),
            project_revision=project.revision,
            ready=has_passed and not has_failed,
            checks=checks,
            observation=observation,
        )
        async with AsyncTransaction() as session:
            saved = await self.projects.service.repo.save_check(
                session, project_id, project.revision, report.model_dump(mode="json")
            )
            if not saved:
                raise ProjectError(409, "Project changed during the connection check; check the new configuration")
        return report
