import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import httpx
import pytest
from app.features.project_management.pipeline_runs.models import PipelineRun, PipelineRunState
from app.features.project_management.pipeline_runs.usecases import lifecycle as run_usecases
from app.features.project_management.pipelines import services
from app.features.project_management.projects.models import ProjectConnection
from sqlalchemy import update
from tests.utils.assertions import assert_status_code

pytestmark = [pytest.mark.e2e, pytest.mark.real_commit]
VERIFICATION = {"workflow": "ci.yml", "required_jobs": ["lint"], "event": "pull_request"}
HEAD = "c" * 40
NOW = datetime(2026, 9, 14, tzinfo=UTC)


def pull(number: int, **overrides) -> dict:
    return {
        "number": number,
        "state": "open",
        "html_url": f"https://github.com/owner/app/pull/{number}",
        "title": f"Add feature {number}",
        "body": "Implement the health endpoint.\n\nCloses #3",
        "head": {"ref": f"feature/{number}", "sha": HEAD, "repo": {"full_name": "owner/app"}},
        "base": {"ref": "main", "sha": "d" * 40, "repo": {"full_name": "owner/app"}},
        **overrides,
    }


def issue(number: int, **overrides) -> dict:
    return {
        "number": number,
        "title": f"Issue {number}",
        "body": "Return 200 with a JSON status.",
        "html_url": f"https://github.com/owner/app/issues/{number}",
        **overrides,
    }


class PullRequestScenario:
    def __init__(self):
        self.pulls = {7: pull(7), 8: pull(8, body="No linked issue")}
        self.issues = {3: issue(3)}
        self.paths: list[str] = []

    def respond(self, request: httpx.Request) -> httpx.Response:
        assert request.method == "GET", "Enrollment must never mutate GitHub"
        path = request.url.path
        self.paths.append(path)
        kind, _, number = path.removeprefix("/repos/owner/app/").partition("/")
        store = {"pulls": self.pulls, "issues": self.issues}.get(kind)
        if store is None or not number.isdigit():
            raise AssertionError(f"Unexpected GitHub request: {path}")
        item = store.get(int(number))
        if item is None:
            return httpx.Response(404, json={"message": "upstream-sensitive-body"})
        return httpx.Response(200, json=item)


@pytest.fixture
def github(monkeypatch) -> PullRequestScenario:
    scenario = PullRequestScenario()

    def create_client(token):
        assert token == "github-test-token"
        return httpx.AsyncClient(base_url="https://api.github.com", transport=httpx.MockTransport(scenario.respond))

    monkeypatch.setattr(services, "create_github_client", create_client)
    return scenario


@pytest.fixture
async def project(client, github) -> dict:
    connector = await client.post(
        "/api/v1/connectors",
        json={"name": "github-account", "provider": "github", "credentials": {"token": "github-test-token"}},
    )
    assert_status_code(connector, 201)
    response = await client.post(
        "/api/v1/projects",
        json={
            "name": "Application",
            "repository": "owner/app",
            "github_connector_id": connector.json()["id"],
            "verification": VERIFICATION,
        },
    )
    assert_status_code(response, 201)
    return response.json()


async def enroll(client, project: dict, number: int = 7) -> httpx.Response:
    return await client.post(f"/api/v1/projects/{project['id']}/runs", json={"pull_number": number})


class TestPullRequestEnrollment:
    async def test_enrolls_an_open_pull_request_with_its_linked_issues(self, client, project, github):
        response = await enroll(client, project)

        assert_status_code(response, 201)
        run = response.json()
        assert run["state"] == "queued"
        assert run["pull_number"] == 7
        assert run["pull_url"] == "https://github.com/owner/app/pull/7"
        assert run["branch"] == "feature/7"
        assert run["pull_snapshot"]["head_sha"] == HEAD
        assert run["pull_snapshot"]["base_ref"] == "main"
        assert run["pull_snapshot"]["linked_issues"] == [
            {
                "number": 3,
                "title": "Issue 3",
                "body": "Return 200 with a JSON status.",
                "url": "https://github.com/owner/app/issues/3",
            }
        ]
        assert github.paths == ["/repos/owner/app/pulls/7", "/repos/owner/app/issues/3"]

        detail = await client.get(f"/api/v1/pipeline-runs/{run['id']}")
        assert_status_code(detail, 200)
        assert detail.json() == run
        listing = await client.get("/api/v1/pipeline-runs", params={"project_id": project["id"]})
        assert listing.json()["items"] == [run]

    async def test_different_pull_requests_can_enroll_but_duplicate_pull_is_blocked_before_reading_github(
        self, client, project, github
    ):
        assert_status_code(await enroll(client, project), 201)
        reads = len(github.paths)

        response = await enroll(client, project, 8)

        assert_status_code(response, 201)
        reads = len(github.paths)
        response = await enroll(client, project, 8)

        assert_status_code(response, 409)
        assert response.json()["detail"] == "This pull request already has an active pipeline run"
        assert len(github.paths) == reads

    async def test_a_finished_run_frees_the_project_for_the_next_pull_request(self, client, project, github, session):
        first = await enroll(client, project)
        assert_status_code(first, 201)
        await session.execute(
            update(PipelineRun)
            .where(PipelineRun.id == UUID(first.json()["id"]))
            .values(state=PipelineRunState.COMPLETED)
        )
        await session.commit()

        second = await enroll(client, project, 8)

        assert_status_code(second, 201)
        assert second.json()["pull_snapshot"]["linked_issues"] == []

    @pytest.mark.parametrize(
        ("pull_overrides", "issue_overrides", "detail"),
        [
            ({"state": "closed"}, {}, "Only open pull requests can be enrolled"),
            (
                {"head": {"ref": "feature/7", "sha": HEAD, "repo": {"full_name": "someone/app"}}},
                {},
                "Fork pull requests are not supported",
            ),
            ({"body": "@codex please implement"}, {}, "Remove @codex from the pull request title and body"),
            ({"title": "@Codex add feature"}, {}, "Remove @codex from the pull request title and body"),
            ({}, {"body": "cc @codex"}, "Remove @codex from issue #3"),
        ],
    )
    async def test_unsafe_pull_requests_are_rejected_without_creating_a_run(
        self, client, project, github, pull_overrides, issue_overrides, detail
    ):
        github.pulls[7] = pull(7, **pull_overrides)
        github.issues[3] = issue(3, **issue_overrides)

        response = await enroll(client, project)

        assert_status_code(response, 422)
        assert response.json()["detail"].startswith(detail)
        assert (await client.get("/api/v1/pipeline-runs")).json()["total_count"] == 0

    async def test_missing_pull_request_is_not_found_without_leaking_upstream_body(self, client, project, github):
        response = await enroll(client, project, 99)

        assert_status_code(response, 404)
        assert "upstream-sensitive-body" not in response.text

    async def test_a_missing_linked_issue_is_rejected(self, client, project, github):
        github.issues.clear()

        response = await enroll(client, project)

        assert_status_code(response, 422)
        assert response.json()["detail"] == "Linked issue #3 was not found"

    async def test_a_closing_reference_to_a_pull_request_is_not_a_linked_issue(self, client, project, github):
        github.issues[3] = issue(3, pull_request={"url": "https://api.github.com/repos/owner/app/pulls/3"})

        response = await enroll(client, project)

        assert_status_code(response, 201)
        assert response.json()["pull_snapshot"]["linked_issues"] == []

    async def test_disabled_project_is_rejected_without_reading_github(self, client, project, github):
        updated = await client.put(
            f"/api/v1/projects/{project['id']}",
            json={
                "name": project["name"],
                "repository": project["repository"],
                "github_connector_id": project["github_connector_id"],
                "verification": project["verification"],
                "enabled": False,
                "expected_revision": project["revision"],
            },
        )
        assert_status_code(updated, 200)

        response = await enroll(client, project)

        assert_status_code(response, 422)
        assert not github.paths

    async def test_project_edit_during_the_read_discards_the_enrollment(
        self, client, project, github, session, monkeypatch
    ):
        original = run_usecases.read_pull_request

        async def read_then_edit(reader, repository, number):
            snapshot = await original(reader, repository, number)
            await session.execute(
                update(ProjectConnection)
                .where(ProjectConnection.id == UUID(project["id"]))
                .values(revision=ProjectConnection.revision + 1)
            )
            await session.commit()
            return snapshot

        monkeypatch.setattr(run_usecases, "read_pull_request", read_then_edit)

        response = await enroll(client, project)

        assert_status_code(response, 409)
        assert response.json()["detail"] == "Project changed during pull request enrollment; retry"

    async def test_run_history_prevents_project_deletion(self, client, project, github):
        assert_status_code(await enroll(client, project), 201)

        response = await client.delete(f"/api/v1/projects/{project['id']}")

        assert_status_code(response, 409)
        assert response.json()["detail"] == "Pipeline run history prevents deleting this project"


class TestPipelineRunLease:
    async def enroll_run(self, client, project) -> str:
        response = await enroll(client, project)
        assert_status_code(response, 201)
        return response.json()["id"]

    async def test_lease_is_exclusive_renewable_and_releasable(self, client, project, github):
        run_id = await self.enroll_run(client, project)
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

    async def test_expired_lease_is_reclaimed_with_a_new_token(self, client, project, github, session):
        run_id = await self.enroll_run(client, project)
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
    async def setup_run(self, client, project) -> tuple[dict, dict]:
        enrolled = await enroll(client, project)
        assert_status_code(enrolled, 201)
        run = enrolled.json()
        leased = await client.post(
            f"/api/v1/pipeline-runs/{run['id']}/lease",
            json={"owner": "dispatcher-a", "ttl_seconds": 60},
        )
        assert_status_code(leased, 200)
        return run, leased.json()

    async def test_prepares_one_immutable_idempotent_attempt(self, client, project, github, session):
        run, lease = await self.setup_run(client, project)
        payload = {"owner": lease["owner"], "token": lease["token"], "expected_run_revision": run["revision"]}

        first = await client.post(f"/api/v1/pipeline-runs/{run['id']}/attempts/implementation", json=payload)
        assert_status_code(first, 200)
        body = first.json()
        assert body["created"] is True
        assert body["run_revision"] == run["revision"] + 1
        assert body["attempt"]["state"] == "planned"
        assert body["attempt"]["kind"] == "implementation"
        assert body["request"]["repository"] == project["repository"]
        assert body["request"]["pull_request"] == run["pull_snapshot"]
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

        await session.execute(
            update(PipelineRun)
            .where(PipelineRun.id == UUID(run["id"]))
            .values(pull_snapshot={**run["pull_snapshot"], "title": "Changed after preparation"})
        )
        await session.commit()
        changed = await client.post(f"/api/v1/pipeline-runs/{run['id']}/attempts/implementation", json=payload)
        assert_status_code(changed, 409)
        assert changed.json()["detail"] == "The active attempt was prepared with a different request"

    async def test_stale_lease_cannot_prepare_an_attempt(self, client, project, github):
        run, lease = await self.setup_run(client, project)

        response = await client.post(
            f"/api/v1/pipeline-runs/{run['id']}/attempts/implementation",
            json={"owner": lease["owner"], "token": str(uuid4()), "expected_run_revision": run["revision"]},
        )

        assert_status_code(response, 409)

    async def test_project_edit_prevents_preparing_stale_run(self, client, project, github, session):
        run, lease = await self.setup_run(client, project)
        await session.execute(
            update(ProjectConnection)
            .where(ProjectConnection.id == UUID(project["id"]))
            .values(revision=ProjectConnection.revision + 1)
        )
        await session.commit()

        response = await client.post(
            f"/api/v1/pipeline-runs/{run['id']}/attempts/implementation",
            json={"owner": lease["owner"], "token": lease["token"], "expected_run_revision": run["revision"]},
        )

        assert_status_code(response, 409)
        assert response.json()["detail"] == "Project changed after this pipeline run was enrolled"
