"""Scheduled Jules sessions: admitted by the AI catalog gateway, created through the Jules API, tracked to the end.

The hub keeps only session state and links; reports and changes stay in Jules or the pull requests it opens.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.features.ai_catalogs.models import (
    SESSION_DISPATCHING,
    SESSION_TERMINAL_STATES,
    AICatalogKind,
    AICatalogSession,
)
from app.features.ai_catalogs.policies.base import utc
from app.features.ai_catalogs.services import CATALOG_CONNECTOR_PROVIDERS, AICatalogService
from app.features.configuration.connectors.crypto import ConnectorCredentialCipher, EncryptedCredentials
from app.features.configuration.connectors.models import Connector
from app.features.execution.tasks.domains.jules.client import (
    SESSION_NAME,
    JulesApiError,
    JulesClient,
    create_jules_client,
)
from app.features.project_management.projects.services import ProjectError
from app_layer_base.core.database.transaction import AsyncTransaction
from pydantic import BaseModel, ConfigDict, Field

SESSION_MARKER = "hub-session"
# Past this age an unconfirmed create that reconciliation cannot find is presumed lost.
UNCONFIRMED_SESSION_TIMEOUT = timedelta(hours=1)


class JulesSessionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_key: str = Field(default="personal-jules", min_length=1, max_length=100)
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", description="GitHub owner/repo")
    starting_branch: str = Field(default="main", min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=20_000)
    auto_create_pr: bool = Field(default=False, description="Let Jules open a pull request with its changes")


class JulesSyncPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_key: str = Field(default="personal-jules", min_length=1, max_length=100)


class JulesSessionService:
    def __init__(self, catalogs: AICatalogService, cipher: ConnectorCredentialCipher) -> None:
        self.catalogs = catalogs
        self.cipher = cipher

    async def start(self, payload: JulesSessionPayload, schedule_config_id: UUID | None) -> UUID:
        """Refresh tracked sessions, then start one new session if the catalog admits it."""
        catalog_id, api_key = await self._catalog_access(payload.catalog_key)
        async with create_jules_client(api_key) as http:
            client = JulesClient(http)
            await self._observe(client, catalog_id)
            session_id = uuid4()
            title = f"{payload.title} [{SESSION_MARKER}:{session_id}]"
            async with AsyncTransaction() as session:
                admission = await self.catalogs.request_dispatch(
                    session, catalog_id, None, f"session:{session_id}", datetime.now(UTC)
                )
                if admission.rejection is not None:
                    # Keep what the policy recorded while rejecting, such as a daily hold it has just reached.
                    await session.commit()
                    raise ProjectError(409, admission.rejection)
                session.add(
                    AICatalogSession(
                        id=session_id,
                        ai_catalog_id=catalog_id,
                        schedule_config_id=schedule_config_id,
                        title=title,
                        state=SESSION_DISPATCHING,
                    )
                )
            try:
                remote = await client.create_session(
                    repository=payload.repository,
                    starting_branch=payload.starting_branch,
                    prompt=payload.prompt,
                    title=title,
                    auto_create_pr=payload.auto_create_pr,
                )
            except JulesApiError as exc:
                await self._record_create_failure(session_id, catalog_id, exc)
                raise ProjectError(exc.status_code if exc.status_code in (422, 429) else 502, str(exc)) from None
            async with AsyncTransaction() as session:
                row = await session.get(AICatalogSession, session_id, with_for_update=True)
                if row is not None:
                    self._apply(row, remote, datetime.now(UTC))
        return session_id

    async def sync(self, catalog_key: str) -> None:
        """Refresh unfinished sessions so finished ones release catalog concurrency."""
        catalog_id, api_key = await self._catalog_access(catalog_key)
        async with create_jules_client(api_key) as http:
            await self._observe(JulesClient(http), catalog_id)

    async def _catalog_access(self, catalog_key: str) -> tuple[UUID, str]:
        async with AsyncTransaction() as session:
            catalog = await self.catalogs.repo.get_by_key(session, catalog_key)
            if catalog is None or catalog.kind != AICatalogKind.JULES:
                raise ProjectError(422, f"'{catalog_key}' is not a Jules AI catalog")
            if catalog.connector_id is None:
                raise ProjectError(422, "Assign a Jules connector to the catalog before starting sessions")
            connector = await session.get(Connector, catalog.connector_id)
            provider = CATALOG_CONNECTOR_PROVIDERS[AICatalogKind.JULES]
            if connector is None or not connector.enabled or connector.provider != provider:
                raise ProjectError(422, "The catalog's Jules connector is missing, disabled, or of another provider")
            catalog_id, connector_id = catalog.id, connector.id
            encrypted = EncryptedCredentials(
                ciphertext=connector.credentials_ciphertext,
                nonce=connector.credentials_nonce,
                key_version=connector.credential_key_version,
            )
        credentials = await self.cipher.decrypt(connector_id, provider, encrypted)
        api_key = credentials.get("token")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ProjectError(422, "The Jules connector's credentials must hold the API key as token")
        return catalog_id, api_key

    async def _observe(self, client: JulesClient, catalog_id: UUID) -> None:
        async with AsyncTransaction() as session:
            tracked = [
                (row.id, row.external_name, row.title, row.created_at)
                for row in await self.catalogs.repo.list_unfinished_sessions(session, catalog_id)
            ]
        for session_id, name, title, created_at in tracked:
            try:
                remote = await client.get_session(name) if name else await client.find_session_by_title(title)
            except JulesApiError:
                # Observation retries on the next run; it never blocks starting new work.
                continue
            now = datetime.now(UTC)
            async with AsyncTransaction() as session:
                row = await session.get(AICatalogSession, session_id, with_for_update=True)
                if row is None or row.state in SESSION_TERMINAL_STATES:
                    continue
                if remote is not None:
                    self._apply(row, remote, now)
                elif now - utc(created_at) >= UNCONFIRMED_SESSION_TIMEOUT:
                    row.state = "failed"
                    row.failure_detail = "Jules never confirmed the session; its creation is presumed lost"
                    row.observed_at = now

    async def _record_create_failure(self, session_id: UUID, catalog_id: UUID, exc: JulesApiError) -> None:
        if exc.status_code is None or exc.status_code >= 500:
            # The session may still have been created; title reconciliation settles it on a later run.
            return
        async with AsyncTransaction() as session:
            row = await session.get(AICatalogSession, session_id, with_for_update=True)
            if row is not None:
                row.state = "failed"
                row.failure_detail = str(exc)
            if exc.status_code == 429:
                # Jules does not document its limit error; a 429 is treated as its task cap being reached.
                await self.catalogs.record_quota_event(session, catalog_id, datetime.now(UTC))

    @staticmethod
    def _apply(row: AICatalogSession, remote: dict[str, Any], now: datetime) -> None:
        name = remote.get("name")
        if isinstance(name, str) and SESSION_NAME.fullmatch(name):
            row.external_name = name
        state = remote.get("state")
        if isinstance(state, str) and state:
            row.state = state.lower()[:40]
        url = remote.get("url")
        if isinstance(url, str):
            row.url = url[:2048]
        for output in remote.get("outputs") or []:
            pull_request = output.get("pullRequest") if isinstance(output, dict) else None
            if isinstance(pull_request, dict) and isinstance(pull_request.get("url"), str):
                row.pull_request_url = pull_request["url"][:2048]
        row.observed_at = now
