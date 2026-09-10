import asyncio
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from app.features.connectors.crypto import ConnectorCredentialCipher, EncryptedCredentials
from app.features.pipelines.github import GitHubActionsReader, GitHubObservationError, create_github_client
from app.features.pipelines.repos import PipelineObservationRepository
from app.features.pipelines.schemas import PipelineObservation, PipelineObservationConfig
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
        # Keep network I/O outside the database transaction.
        async with AsyncTransaction() as session:
            connector = await self.repo.get_connector(session, config.github_connector_id)
            if connector is None or not connector.enabled or connector.provider != "github":
                raise PipelineConfigurationError("An enabled GitHub connector is required")
            connector_id, provider = connector.id, connector.provider
            encrypted = EncryptedCredentials(
                connector.credentials_ciphertext, connector.credentials_nonce, connector.credential_key_version
            )
        credentials = await self.cipher.decrypt(connector_id, provider, encrypted)
        token = credentials.get("token")
        if not isinstance(token, str) or not token.strip():
            raise PipelineConfigurationError("GitHub connector credentials must contain a non-empty token")
        async with create_github_client(token) as client:
            reader = GitHubActionsReader(client)
            pulls = [await reader.observe_pull(config, number) for number in config.pull_numbers]
        return PipelineObservation(observed_at=datetime.now(UTC), config=config, pulls=pulls)

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


class PipelineObservationQueryService:
    """Reading a stored report does not require decrypting connector credentials."""

    def __init__(self, repo: Annotated[PipelineObservationRepository, Depends()]):
        self.repo = repo

    async def get(self, schedule_id: UUID) -> PipelineObservation | None:
        async with AsyncTransaction() as session:
            schedule = await self.repo.get_schedule(session, schedule_id)
            if schedule is None or schedule.task_func != OBSERVATION_TASK:
                return None
            raw = await self.repo.load(session, schedule_id)
        if raw is None or raw.get("kind") != "pipeline_observation":
            return None
        try:
            report = PipelineObservation.model_validate(raw)
            config = PipelineObservationConfig.model_validate(schedule.payload)
        except ValidationError:
            return None
        if config != report.config:
            return None
        return report
