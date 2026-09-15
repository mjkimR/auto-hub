import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from app.features.ai_catalogs.models import (
    AICatalog,
    AICatalogDispatch,
    AICatalogKind,
    AICatalogSession,
    AICatalogState,
)
from app.features.ai_catalogs.repos import AICatalogRepository
from app.features.ai_catalogs.services import AICatalogService
from app.features.configuration.connectors.models import Connector
from app.features.execution.tasks.domains.jules import service as jules_service
from app.features.execution.tasks.domains.jules.client import JULES_API_BASE_URL
from app.features.execution.tasks.domains.jules.service import JulesSessionPayload, JulesSessionService
from app.features.project_management.projects.services import ProjectError
from sqlalchemy import select

pytestmark = pytest.mark.e2e


class FakeJules:
    def __init__(self) -> None:
        self.responses: dict[tuple[str, str], tuple[int, dict]] = {}
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self.responses[(request.method, request.url.path)]
        return httpx.Response(status, json=body)


@pytest.fixture
def jules(monkeypatch) -> FakeJules:
    fake = FakeJules()
    monkeypatch.setattr(
        jules_service,
        "create_jules_client",
        lambda api_key: httpx.AsyncClient(
            base_url=JULES_API_BASE_URL,
            headers={"X-Goog-Api-Key": api_key},
            transport=httpx.MockTransport(fake.handle),
        ),
    )
    return fake


async def make_catalog(session, *, limit: int = 100, with_connector: bool = True) -> SimpleNamespace:
    connector_id = None
    if with_connector:
        connector = Connector(
            name=f"jules-{uuid4().hex[:8]}",
            provider="jules",
            config={},
            enabled=True,
            credentials_ciphertext=b"sealed",
            credentials_nonce=b"0" * 12,
            credential_key_version="test",
        )
        session.add(connector)
        await session.flush()
        connector_id = connector.id
    catalog = AICatalog(
        key=f"jules-{uuid4().hex[:8]}",
        name="Jules",
        kind=AICatalogKind.JULES,
        adapter="jules-api",
        connector_id=connector_id,
        enabled=True,
        availability_state=AICatalogState.NORMAL,
        configured_concurrency=15,
        policy_config={"daily_task_limit": limit, "window": "rolling", "timezone": "UTC"},
        revision=1,
    )
    session.add(catalog)
    await session.flush()
    created = SimpleNamespace(id=catalog.id, key=catalog.key)
    await session.commit()
    return created


def make_service() -> JulesSessionService:
    cipher = MagicMock()
    cipher.decrypt = AsyncMock(return_value={"token": "jules-key"})
    return JulesSessionService(AICatalogService(AICatalogRepository()), cipher)


def payload(catalog_key: str, **overrides) -> JulesSessionPayload:
    return JulesSessionPayload(
        catalog_key=catalog_key,
        repository="owner/app",
        title="Weekly hygiene report",
        prompt="Report stale dependencies.",
        **overrides,
    )


async def sessions_of(session, catalog_id) -> list[AICatalogSession]:
    session.expire_all()
    return list(
        (await session.scalars(select(AICatalogSession).where(AICatalogSession.ai_catalog_id == catalog_id))).all()
    )


async def test_an_admitted_session_is_created_counted_and_tracked(client, session, jules):
    catalog = await make_catalog(session)
    jules.responses[("POST", "/v1alpha/sessions")] = (
        200,
        {"name": "sessions/42", "state": "QUEUED", "url": "https://jules.google/session/42"},
    )

    session_id = await make_service().start(payload(catalog.key, auto_create_pr=True), None)

    [request] = jules.requests
    body = json.loads(request.content)
    assert request.headers["X-Goog-Api-Key"] == "jules-key"
    assert body["sourceContext"] == {
        "source": "sources/github/owner/app",
        "githubRepoContext": {"startingBranch": "main"},
    }
    assert body["automationMode"] == "AUTO_CREATE_PR"
    assert body["title"] == f"Weekly hygiene report [hub-session:{session_id}]"
    [tracked] = await sessions_of(session, catalog.id)
    assert (tracked.id, tracked.state, tracked.external_name) == (session_id, "queued", "sessions/42")
    ledger = await session.scalars(
        select(AICatalogDispatch.dispatch_key).where(AICatalogDispatch.ai_catalog_id == catalog.id)
    )
    assert ledger.all() == [f"session:{session_id}"]


async def test_reaching_the_daily_limit_holds_the_catalog_without_calling_jules(client, session, jules):
    catalog = await make_catalog(session, limit=1)
    session.add(
        AICatalogDispatch(
            ai_catalog_id=catalog.id,
            dispatch_key="session:earlier",
            admitted_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await session.commit()

    with pytest.raises(ProjectError) as rejected:
        await make_service().start(payload(catalog.key), None)

    assert rejected.value.status_code == 409
    assert jules.requests == []
    assert await sessions_of(session, catalog.id) == []
    held = await session.get(AICatalog, catalog.id)
    assert held is not None and held.availability_state == AICatalogState.QUOTA_BLOCKED


async def test_a_rate_limited_create_fails_the_session_and_holds_the_catalog(client, session, jules):
    catalog = await make_catalog(session)
    jules.responses[("POST", "/v1alpha/sessions")] = (429, {"error": {"status": "RESOURCE_EXHAUSTED"}})

    with pytest.raises(ProjectError) as rejected:
        await make_service().start(payload(catalog.key), None)

    assert rejected.value.status_code == 429
    [tracked] = await sessions_of(session, catalog.id)
    assert tracked.state == "failed"
    held = await session.get(AICatalog, catalog.id)
    assert held is not None and held.availability_state == AICatalogState.QUOTA_BLOCKED


async def test_sync_adopts_an_unconfirmed_session_and_releases_a_finished_one(client, session, jules):
    catalog = await make_catalog(session)
    unconfirmed_id, running_id = uuid4(), uuid4()
    unconfirmed_title = f"Report [hub-session:{unconfirmed_id}]"
    session.add_all(
        [
            AICatalogSession(id=unconfirmed_id, ai_catalog_id=catalog.id, title=unconfirmed_title, state="dispatching"),
            AICatalogSession(
                id=running_id,
                ai_catalog_id=catalog.id,
                title="Hygiene",
                state="in_progress",
                external_name="sessions/7",
            ),
        ]
    )
    await session.commit()
    jules.responses[("GET", "/v1alpha/sessions")] = (
        200,
        {"sessions": [{"name": "sessions/8", "title": unconfirmed_title, "state": "IN_PROGRESS"}]},
    )
    jules.responses[("GET", "/v1alpha/sessions/7")] = (
        200,
        {
            "name": "sessions/7",
            "state": "COMPLETED",
            "outputs": [{"pullRequest": {"url": "https://github.com/owner/app/pull/9"}}],
        },
    )

    await make_service().sync(catalog.key)

    tracked = {row.id: row for row in await sessions_of(session, catalog.id)}
    assert (tracked[unconfirmed_id].state, tracked[unconfirmed_id].external_name) == ("in_progress", "sessions/8")
    assert (tracked[running_id].state, tracked[running_id].pull_request_url) == (
        "completed",
        "https://github.com/owner/app/pull/9",
    )
    assert await AICatalogRepository().active_dispatch_count(session, catalog.id) == 1


async def test_a_catalog_without_a_jules_connector_is_rejected(client, session, jules):
    catalog = await make_catalog(session, with_connector=False)

    with pytest.raises(ProjectError) as rejected:
        await make_service().start(payload(catalog.key), None)

    assert rejected.value.status_code == 422
    assert jules.requests == []
