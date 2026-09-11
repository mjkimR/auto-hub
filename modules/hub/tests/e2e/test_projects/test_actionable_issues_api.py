import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import httpx
import pytest
from app.features.pipeline_runs.models import PipelineRun, PipelineRunState
from app.features.projects import linear
from app.features.projects.models import ProjectConnection
from app.features.projects.schemas import ActionableIssueSelection
from sqlalchemy import update
from tests.utils.assertions import assert_status_code

pytestmark = [pytest.mark.e2e, pytest.mark.real_commit]
VERIFICATION = {"workflow": "ci.yml", "required_jobs": ["lint"], "event": "pull_request"}
NOW = datetime(2026, 9, 11, tzinfo=UTC)


def issue(
    number: int,
    *,
    priority: int = 3,
    state_type: str = "unstarted",
    description: str | None = "Acceptance criteria",
    blocker_states: tuple[str, ...] = (),
) -> dict:
    return {
        "id": str(UUID(int=number)),
        "identifier": f"HUB-{number}",
        "title": f"Issue {number}",
        "description": description,
        "priority": priority,
        "createdAt": (NOW + timedelta(minutes=number)).isoformat().replace("+00:00", "Z"),
        "updatedAt": NOW.isoformat().replace("+00:00", "Z"),
        "url": f"https://linear.app/example/issue/HUB-{number}",
        "state": {"type": state_type},
        "inverseRelations": {
            "nodes": [
                {
                    "type": "blocks",
                    "issue": {
                        "id": str(UUID(int=100 + index)),
                        "identifier": f"HUB-{100 + index}",
                        "state": {"type": blocker_state},
                    },
                }
                for index, blocker_state in enumerate(blocker_states)
            ],
            "pageInfo": {"hasNextPage": False},
        },
    }


class LinearIssueScenario:
    def __init__(self):
        self.project_id: str | None = None
        self.pages: list[list[dict]] = [[]]
        self.requests: list[dict] = []
        self.errors: list[dict] | None = None

    def respond(self, request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        payload = json.loads(request.content)
        self.requests.append(payload)
        assert "HubProjectIssues" in payload["query"]
        assert "inverseRelations(first: 10)" in payload["query"]
        if self.errors:
            return httpx.Response(200, json={"errors": self.errors})
        after = payload["variables"]["after"]
        page_index = 0 if after is None else int(after.removeprefix("cursor-"))
        has_next = page_index + 1 < len(self.pages)
        return httpx.Response(
            200,
            json={
                "data": {
                    "project": {
                        "id": self.project_id,
                        "issues": {
                            "nodes": self.pages[page_index],
                            "pageInfo": {
                                "hasNextPage": has_next,
                                "endCursor": f"cursor-{page_index + 1}" if has_next else None,
                            },
                        },
                    }
                }
            },
        )


@pytest.fixture
def linear_issue_scenario(monkeypatch):
    scenario = LinearIssueScenario()

    def create_client(token: str):
        assert token == "linear-test-token"
        return httpx.AsyncClient(base_url="https://api.linear.app", transport=httpx.MockTransport(scenario.respond))

    monkeypatch.setattr(linear, "create_linear_client", create_client)
    return scenario


async def create_connector(client, provider: str) -> str:
    response = await client.post(
        "/api/v1/connectors",
        json={"name": f"{provider}-account", "provider": provider, "credentials": {"token": f"{provider}-test-token"}},
    )
    assert_status_code(response, 201)
    return response.json()["id"]


@pytest.fixture
async def project(client, linear_issue_scenario) -> dict:
    github_connector_id = await create_connector(client, "github")
    linear_connector_id = await create_connector(client, "linear")
    project_id = str(uuid4())
    linear_issue_scenario.project_id = project_id
    response = await client.post(
        "/api/v1/projects",
        json={
            "name": "Application",
            "repository": "owner/app",
            "linear_project_id": project_id,
            "github_connector_id": github_connector_id,
            "linear_connector_id": linear_connector_id,
            "verification": VERIFICATION,
        },
    )
    assert_status_code(response, 201)
    return response.json()


class TestActionableIssueSelection:
    async def test_selects_one_issue_across_pages_and_reports_diagnostics(self, client, project, linear_issue_scenario):
        linear_issue_scenario.pages = [
            [issue(1, priority=4, description=None), issue(2, priority=1, blocker_states=("started",))],
            [issue(3, priority=1), issue(4, state_type="completed")],
        ]

        response = await client.get(f"/api/v1/projects/{project['id']}/issues/actionable")

        assert_status_code(response, 200)
        assert response.json()["selected"]["identifier"] == "HUB-3"
        assert response.json()["selected"]["state_type"] == "unstarted"
        assert response.json()["inspected_count"] == 4
        assert response.json()["actionable_count"] == 2
        assert response.json()["blocked_count"] == 1
        assert [request["variables"]["after"] for request in linear_issue_scenario.requests] == [None, "cursor-1"]

    async def test_identical_duplicate_issue_is_counted_once(self, client, project, linear_issue_scenario):
        same_issue = issue(1)
        linear_issue_scenario.pages = [[same_issue], [same_issue]]

        response = await client.get(f"/api/v1/projects/{project['id']}/issues/actionable")

        assert_status_code(response, 200)
        assert response.json()["inspected_count"] == 1
        assert response.json()["selected"]["identifier"] == "HUB-1"

    async def test_rate_limit_error_is_specific_and_upstream_body_is_hidden(
        self, client, project, linear_issue_scenario
    ):
        linear_issue_scenario.errors = [{"message": "linear-sensitive-body", "extensions": {"code": "RATELIMITED"}}]

        response = await client.get(f"/api/v1/projects/{project['id']}/issues/actionable")

        assert_status_code(response, 429)
        assert response.json()["detail"] == "Linear issue query was rate limited"
        assert "linear-sensitive-body" not in response.text

    async def test_missing_linear_connector_is_rejected_without_external_call(self, client, linear_issue_scenario):
        github_connector_id = await create_connector(client, "github")
        response = await client.post(
            "/api/v1/projects",
            json={
                "name": "No Linear",
                "repository": "owner/no-linear",
                "linear_project_id": str(uuid4()),
                "github_connector_id": github_connector_id,
                "linear_connector_id": None,
                "verification": VERIFICATION,
            },
        )
        assert_status_code(response, 201)

        selection = await client.get(f"/api/v1/projects/{response.json()['id']}/issues/actionable")

        assert_status_code(selection, 422)
        assert not linear_issue_scenario.requests

    async def test_disabled_project_is_rejected_without_external_call(self, client, project, linear_issue_scenario):
        updated = await client.put(
            f"/api/v1/projects/{project['id']}",
            json={
                "name": project["name"],
                "repository": project["repository"],
                "linear_project_id": project["linear_project_id"],
                "github_connector_id": project["github_connector_id"],
                "linear_connector_id": project["linear_connector_id"],
                "verification": project["verification"],
                "enabled": False,
                "expected_revision": project["revision"],
            },
        )
        assert_status_code(updated, 200)

        response = await client.get(f"/api/v1/projects/{project['id']}/issues/actionable")

        assert_status_code(response, 422)
        assert not linear_issue_scenario.requests

    async def test_project_edit_during_query_discards_the_result(
        self, client, project, linear_issue_scenario, session, monkeypatch
    ):
        async def select_after_edit(reader, project_id, excluded_issue_ids=None):
            await session.execute(
                update(ProjectConnection)
                .where(ProjectConnection.id == UUID(project["id"]))
                .values(revision=ProjectConnection.revision + 1)
            )
            await session.commit()
            return ActionableIssueSelection(selected=None, inspected_count=0, actionable_count=0, blocked_count=0)

        monkeypatch.setattr(linear.LinearIssueReader, "select", select_after_edit)

        response = await client.get(f"/api/v1/projects/{project['id']}/issues/actionable")

        assert_status_code(response, 409)
        assert "Project changed during" in response.json()["detail"]


class TestPipelineRunAcquisition:
    async def test_acquires_then_resumes_the_active_run(self, client, project, linear_issue_scenario):
        linear_issue_scenario.pages = [[issue(1, priority=1), issue(2, priority=2)]]

        first = await client.post(f"/api/v1/projects/{project['id']}/runs/acquire")
        assert_status_code(first, 200)
        first_body = first.json()
        assert first_body["created"] is True
        assert first_body["run"]["linear_issue_identifier"] == "HUB-1"
        assert first_body["run"]["state"] == "queued"
        assert first_body["run"]["branch"] == "codex/hub-1"
        assert len(linear_issue_scenario.requests) == 1

        second = await client.post(f"/api/v1/projects/{project['id']}/runs/acquire")
        assert_status_code(second, 200)
        assert second.json()["created"] is False
        assert second.json()["run"]["id"] == first_body["run"]["id"]
        assert len(linear_issue_scenario.requests) == 1

        detail = await client.get(f"/api/v1/pipeline-runs/{first_body['run']['id']}")
        assert_status_code(detail, 200)
        assert detail.json() == second.json()["run"]

        listing = await client.get("/api/v1/pipeline-runs", params={"project_id": project["id"]})
        assert_status_code(listing, 200)
        assert listing.json()["total_count"] == 1
        assert listing.json()["items"] == [second.json()["run"]]

    async def test_completed_issue_is_excluded_from_the_next_run(self, client, project, linear_issue_scenario, session):
        linear_issue_scenario.pages = [[issue(1, priority=1), issue(2, priority=2)]]
        first = await client.post(f"/api/v1/projects/{project['id']}/runs/acquire")
        assert_status_code(first, 200)
        first_id = UUID(first.json()["run"]["id"])
        await session.execute(
            update(PipelineRun).where(PipelineRun.id == first_id).values(state=PipelineRunState.COMPLETED)
        )
        await session.commit()

        second = await client.post(f"/api/v1/projects/{project['id']}/runs/acquire")

        assert_status_code(second, 200)
        assert second.json()["created"] is True
        assert second.json()["run"]["linear_issue_identifier"] == "HUB-2"

    async def test_no_actionable_issue_does_not_create_a_run(self, client, project, linear_issue_scenario):
        linear_issue_scenario.pages = [[issue(1, blocker_states=("started",))]]

        response = await client.post(f"/api/v1/projects/{project['id']}/runs/acquire")

        assert_status_code(response, 200)
        assert response.json()["created"] is False
        assert response.json()["run"] is None
        assert response.json()["selection"]["blocked_count"] == 1

    async def test_run_history_prevents_project_deletion(self, client, project, linear_issue_scenario):
        linear_issue_scenario.pages = [[issue(1)]]
        acquired = await client.post(f"/api/v1/projects/{project['id']}/runs/acquire")
        assert_status_code(acquired, 200)

        response = await client.delete(f"/api/v1/projects/{project['id']}")

        assert_status_code(response, 409)
        assert response.json()["detail"] == "Pipeline run history prevents deleting this project"

    async def test_project_edit_after_selection_discards_the_candidate(
        self, client, project, linear_issue_scenario, session, monkeypatch
    ):
        linear_issue_scenario.pages = [[issue(1)]]
        original_execute = linear.SelectActionableIssueUseCase.execute

        async def execute_after_edit(use_case, project_id, *, excluded_issue_ids=None):
            result = await original_execute(use_case, project_id, excluded_issue_ids=excluded_issue_ids)
            await session.execute(
                update(ProjectConnection)
                .where(ProjectConnection.id == UUID(project["id"]))
                .values(revision=ProjectConnection.revision + 1)
            )
            await session.commit()
            return result

        monkeypatch.setattr(linear.SelectActionableIssueUseCase, "execute", execute_after_edit)

        response = await client.post(f"/api/v1/projects/{project['id']}/runs/acquire")

        assert_status_code(response, 409)
        assert response.json()["detail"] == "Project changed during pipeline run acquisition; retry"


class TestPipelineRunLease:
    async def acquire_run(self, client, project, linear_issue_scenario) -> str:
        linear_issue_scenario.pages = [[issue(1)]]
        response = await client.post(f"/api/v1/projects/{project['id']}/runs/acquire")
        assert_status_code(response, 200)
        return response.json()["run"]["id"]

    async def test_lease_is_exclusive_renewable_and_releasable(self, client, project, linear_issue_scenario):
        run_id = await self.acquire_run(client, project, linear_issue_scenario)
        first = await client.post(
            f"/api/v1/pipeline-runs/{run_id}/lease", json={"owner": "worker-a", "ttl_seconds": 60}
        )
        assert_status_code(first, 200)
        lease = first.json()
        assert lease["owner"] == "worker-a"

        conflict = await client.post(
            f"/api/v1/pipeline-runs/{run_id}/lease", json={"owner": "worker-b", "ttl_seconds": 60}
        )
        assert_status_code(conflict, 409)

        stale = await client.put(
            f"/api/v1/pipeline-runs/{run_id}/lease",
            json={"owner": "worker-a", "token": str(uuid4()), "ttl_seconds": 60},
        )
        assert_status_code(stale, 409)

        renewed = await client.put(
            f"/api/v1/pipeline-runs/{run_id}/lease",
            json={"owner": "worker-a", "token": lease["token"], "ttl_seconds": 120},
        )
        assert_status_code(renewed, 200)
        assert renewed.json()["expires_at"] > lease["expires_at"]

        released = await client.post(
            f"/api/v1/pipeline-runs/{run_id}/lease/release",
            json={"owner": "worker-a", "token": lease["token"], "ttl_seconds": 60},
        )
        assert_status_code(released, 204)

        next_lease = await client.post(
            f"/api/v1/pipeline-runs/{run_id}/lease", json={"owner": "worker-b", "ttl_seconds": 60}
        )
        assert_status_code(next_lease, 200)
        assert next_lease.json()["token"] != lease["token"]

        detail = await client.get(f"/api/v1/pipeline-runs/{run_id}")
        assert_status_code(detail, 200)
        assert "lease_token" not in detail.json()

    async def test_expired_lease_is_reclaimed_with_a_new_token(self, client, project, linear_issue_scenario, session):
        run_id = await self.acquire_run(client, project, linear_issue_scenario)
        first = await client.post(
            f"/api/v1/pipeline-runs/{run_id}/lease", json={"owner": "worker-a", "ttl_seconds": 60}
        )
        assert_status_code(first, 200)
        await session.execute(
            update(PipelineRun)
            .where(PipelineRun.id == UUID(run_id))
            .values(lease_expires_at=NOW - timedelta(seconds=1))
        )
        await session.commit()

        reclaimed = await client.post(
            f"/api/v1/pipeline-runs/{run_id}/lease", json={"owner": "worker-b", "ttl_seconds": 60}
        )

        assert_status_code(reclaimed, 200)
        assert reclaimed.json()["owner"] == "worker-b"
        assert reclaimed.json()["token"] != first.json()["token"]


class TestImplementationAttemptPreparation:
    async def setup_run(self, client, project, linear_issue_scenario) -> tuple[dict, dict]:
        linear_issue_scenario.pages = [[issue(1, description="Return a useful health response")]]
        acquired = await client.post(f"/api/v1/projects/{project['id']}/runs/acquire")
        assert_status_code(acquired, 200)
        run = acquired.json()["run"]
        leased = await client.post(
            f"/api/v1/pipeline-runs/{run['id']}/lease",
            json={"owner": "dispatcher-a", "ttl_seconds": 60},
        )
        assert_status_code(leased, 200)
        return run, leased.json()

    async def test_prepares_one_immutable_idempotent_attempt(self, client, project, linear_issue_scenario):
        run, lease = await self.setup_run(client, project, linear_issue_scenario)
        payload = {
            "owner": lease["owner"],
            "token": lease["token"],
            "expected_run_revision": run["revision"],
            "base_branch": "main",
        }

        first = await client.post(f"/api/v1/pipeline-runs/{run['id']}/attempts/implementation", json=payload)
        assert_status_code(first, 200)
        body = first.json()
        assert body["created"] is True
        assert body["run_revision"] == run["revision"] + 1
        assert body["attempt"]["state"] == "planned"
        assert body["attempt"]["kind"] == "implementation"
        assert body["request"]["repository"] == project["repository"]
        assert body["request"]["base_branch"] == "main"
        assert body["request"]["head_branch"] == "codex/hub-1"
        assert body["request"]["issue"]["description"] == "Return a useful health response"
        assert body["request"]["correlation_marker"] == f"hub-attempt:{body['attempt']['idempotency_key']}"
        canonical = json.dumps(body["request"], sort_keys=True, separators=(",", ":"))
        assert body["attempt"]["request_digest"] == sha256(canonical.encode()).hexdigest()

        repeated = await client.post(f"/api/v1/pipeline-runs/{run['id']}/attempts/implementation", json=payload)
        assert_status_code(repeated, 200)
        assert repeated.json()["created"] is False
        assert repeated.json()["attempt"]["id"] == body["attempt"]["id"]
        assert repeated.json()["request"] == body["request"]

        attempts = await client.get(f"/api/v1/pipeline-runs/{run['id']}/attempts")
        assert_status_code(attempts, 200)
        assert attempts.json()["total_count"] == 1
        assert attempts.json()["items"] == [body["attempt"]]

        changed = await client.post(
            f"/api/v1/pipeline-runs/{run['id']}/attempts/implementation",
            json={**payload, "base_branch": "release"},
        )
        assert_status_code(changed, 409)

    async def test_stale_lease_cannot_prepare_an_attempt(self, client, project, linear_issue_scenario):
        run, lease = await self.setup_run(client, project, linear_issue_scenario)

        response = await client.post(
            f"/api/v1/pipeline-runs/{run['id']}/attempts/implementation",
            json={
                "owner": lease["owner"],
                "token": str(uuid4()),
                "expected_run_revision": run["revision"],
                "base_branch": "main",
            },
        )

        assert_status_code(response, 409)

    async def test_project_edit_prevents_preparing_stale_run(self, client, project, linear_issue_scenario, session):
        run, lease = await self.setup_run(client, project, linear_issue_scenario)
        await session.execute(
            update(ProjectConnection)
            .where(ProjectConnection.id == UUID(project["id"]))
            .values(revision=ProjectConnection.revision + 1)
        )
        await session.commit()

        response = await client.post(
            f"/api/v1/pipeline-runs/{run['id']}/attempts/implementation",
            json={
                "owner": lease["owner"],
                "token": lease["token"],
                "expected_run_revision": run["revision"],
                "base_branch": "main",
            },
        )

        assert_status_code(response, 409)
        assert response.json()["detail"] == "Project changed after this pipeline run was acquired"
