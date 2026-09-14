import asyncio
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from app.features.pipelines import services as pipeline_services
from app.features.pipelines.github import GitHubActionsReader, GitHubObservationError
from app.features.pipelines.services import PipelineConfigurationError, PipelineObservationService
from app.features.projects.schemas import ConnectionCheck, ConnectionCheckItem
from app.features.projects.services import ProjectError
from app.features.projects.usecases import ProjectUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends


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
        github_login = None
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
                if project.github is not None:
                    try:
                        github_login = await self._github_login(project.github.github_connector_id)
                        checks.append(
                            ConnectionCheckItem(
                                name="GitHub identity",
                                status="passed",
                                detail=f"Codex mentions will be posted as @{github_login}. "
                                "It must be the GitHub account linked to Codex.",
                            )
                        )
                    except (GitHubObservationError, PipelineConfigurationError, ProjectError) as exc:
                        checks.append(ConnectionCheckItem(name="GitHub identity", status="failed", detail=str(exc)))
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
            github_login=github_login,
        )
        async with AsyncTransaction() as session:
            saved = await self.projects.service.repo.save_check(
                session, project_id, project.revision, report.model_dump(mode="json")
            )
            if not saved:
                raise ProjectError(409, "Project changed during the connection check; check the new configuration")
        return report

    async def _github_login(self, connector_id: UUID) -> str:
        """Mentions from bot or app identities get no Codex response, so the token must act as a user."""
        token = await self.observer.get_token(connector_id, "github")
        async with pipeline_services.create_github_client(token) as client:
            user = await GitHubActionsReader(client)._get("/user")
        login = user.get("login")
        if not isinstance(login, str) or not login or user.get("type") != "User":
            raise ProjectError(422, "The GitHub token does not act as a user account; Codex mentions need a user PAT")
        return login
