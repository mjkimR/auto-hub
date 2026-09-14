import asyncio
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from app.features.connectors.crypto import ConnectorCredentialCipher, EncryptedCredentials
from app.features.pipelines.github import GitHubActionsReader, GitHubObservationError, create_github_client
from app.features.pipelines.repos import PipelineObservationRepository
from app.features.pipelines.schemas import PipelineObservation, PipelineObservationConfig
from app.features.projects.observation import resolve_project_observation
from app.features.projects.repos import PROJECT_OBSERVATION_TASK, ProjectRepository
from app.features.projects.schemas import ProjectObservationPayload
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends
from pydantic import ValidationError

OBSERVATION_TASK = "pipeline.observe"


class PipelineConfigurationError(ValueError):
    pass


class PipelineObservationService:
    def __init__(
        self,
        repo: Annotated[PipelineObservationRepository, Depends()],
        cipher: Annotated[ConnectorCredentialCipher, Depends()],
    ):
        self.repo = repo
        self.cipher = cipher

    async def observe(self, config: PipelineObservationConfig) -> PipelineObservation:
        try:
            async with asyncio.timeout(60):
                return await self._observe(config)
        except TimeoutError:
            raise GitHubObservationError("Pipeline observation exceeded its 60-second budget") from None

    async def _observe(self, config: PipelineObservationConfig) -> PipelineObservation:
        token = await self.get_token(config.github_connector_id, "github")
        async with create_github_client(token) as client:
            reader = GitHubActionsReader(client)
            pulls = [await reader.observe_pull(config, number) for number in config.pull_numbers]
        return PipelineObservation(observed_at=datetime.now(UTC), config=config, pulls=pulls)

    async def find_pull_request(self, connector_id: UUID, repository: str, head_branch: str) -> dict[str, Any] | None:
        token = await self.get_token(connector_id, "github")
        async with create_github_client(token) as client:
            reader = GitHubActionsReader(client)
            return await reader.find_pull_request(repository, head_branch)

    async def get_token(self, connector_id: UUID, expected_provider: str) -> str:
        # Keep network I/O outside the database transaction.
        async with AsyncTransaction() as session:
            connector = await self.repo.get_connector(session, connector_id)
            if connector is None or not connector.enabled or connector.provider != expected_provider:
                raise PipelineConfigurationError(f"An enabled {expected_provider} connector is required")
            connector_id, provider = connector.id, connector.provider
            encrypted = EncryptedCredentials(
                connector.credentials_ciphertext, connector.credentials_nonce, connector.credential_key_version
            )
        credentials = await self.cipher.decrypt(connector_id, provider, encrypted)
        token = credentials.get("token")
        if not isinstance(token, str) or not token.strip():
            raise PipelineConfigurationError(
                f"{expected_provider} connector credentials must contain a non-empty token"
            )
        return token

    async def observe_and_save(self, config: PipelineObservationConfig, schedule_id: UUID) -> PipelineObservation:
        report = await self.observe(config)
        async with AsyncTransaction() as session:
            schedule = await self.repo.get_schedule(session, schedule_id)
            if schedule is None or schedule.task_func != OBSERVATION_TASK:
                raise PipelineConfigurationError("Observation schedule no longer exists")
            if PipelineObservationConfig.model_validate(schedule.payload) != config:
                raise PipelineConfigurationError("Observation configuration changed during execution")
            await self.repo.save(session, schedule_id, report.model_dump(mode="json"))
        return report

    async def observe_project_and_save(
        self, payload: ProjectObservationPayload, schedule_id: UUID
    ) -> PipelineObservation:
        config, revision = await resolve_project_observation(payload)
        report = await self.observe(config)
        async with AsyncTransaction() as session:
            project = await ProjectRepository().get(session, payload.project_id, lock=True)
            schedule = await self.repo.get_schedule(session, schedule_id)
            if (
                project is None
                or not project.enabled
                or project.revision != revision
                or schedule is None
                or schedule.task_func != PROJECT_OBSERVATION_TASK
                or ProjectObservationPayload.model_validate(schedule.payload) != payload
            ):
                raise PipelineConfigurationError("Project or schedule changed during observation")
            await self.repo.save(session, schedule_id, report.model_dump(mode="json"))
        return report


class PipelineObservationQueryService:
    """Reading a stored report does not require decrypting connector credentials."""

    def __init__(self, repo: Annotated[PipelineObservationRepository, Depends()]):
        self.repo = repo

    async def get(self, schedule_id: UUID) -> PipelineObservation | None:
        async with AsyncTransaction() as session:
            schedule = await self.repo.get_schedule(session, schedule_id)
            if schedule is None or schedule.task_func not in (OBSERVATION_TASK, PROJECT_OBSERVATION_TASK):
                return None
            raw = await self.repo.load(session, schedule_id)
            task_func, payload = schedule.task_func, schedule.payload
        if raw is None or raw.get("kind") != "pipeline_observation":
            return None
        try:
            report = PipelineObservation.model_validate(raw)
            if task_func == PROJECT_OBSERVATION_TASK:
                from app.features.projects.services import ProjectError

                try:
                    config, _ = await resolve_project_observation(ProjectObservationPayload.model_validate(payload))
                except ProjectError:
                    return None
            else:
                config = PipelineObservationConfig.model_validate(payload)
        except ValidationError:
            return None
        if config != report.config:
            return None
        return report
