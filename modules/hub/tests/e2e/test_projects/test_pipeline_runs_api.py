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


async def prepare_run(client, project):
    response = await enroll(client, project)
    assert_status_code(response, 201)
    run = response.json()
    leased = await client.post(f"/api/v1/pipeline-runs/{run['id']}/lease", json={"owner": "recovery-test"})
    assert_status_code(leased, 200)
    lease = leased.json()
    prepared = await client.post(
        f"/api/v1/pipeline-runs/{run['id']}/attempts/implementation",
        json={"owner": lease["owner"], "token": lease["token"], "expected_run_revision": run["revision"]},
    )
    assert_status_code(prepared, 200)
    released = await client.post(
        f"/api/v1/pipeline-runs/{run['id']}/lease/release",
        json={"owner": lease["owner"], "token": lease["token"]},
    )
    assert_status_code(released, 204)
    return run, prepared.json()["attempt"]


class TestRunRecovery:
    async def test_resume_before_attempt_preparation_uses_current_head(self, client, project, github):
        run = (await enroll(client, project)).json()
        root = f"/api/v1/pipeline-runs/{run['id']}"
        assert_status_code(await client.post(f"{root}/pause"), 200)
        github.pulls[7]["head"]["sha"] = "e" * 40
        resumed = await client.post(f"{root}/resume")
        assert_status_code(resumed, 200)
        assert resumed.json()["state"] == "dispatching"
        attempts = (await client.get(f"{root}/attempts")).json()["items"]
        assert len(attempts) == 1
        assert attempts[0]["epoch"] == 2
        assert attempts[0]["request_snapshot"]["pull_request"]["head_sha"] == "e" * 40

    async def test_resume_after_environment_failure_delivers_new_attempt(
        self, client, project, github, session, monkeypatch
    ):
        from app.features.project_management.pipeline_runs.models import ExecutionAttempt

        run, attempt = await prepare_run(client, project)
        await session.execute(update(PipelineRun).where(PipelineRun.id == UUID(run["id"])).values(state="paused"))
        await session.execute(
            update(ExecutionAttempt)
            .where(ExecutionAttempt.id == UUID(attempt["id"]))
            .values(state="failed", finished_at=NOW, failure_code="CI_ENVIRONMENT_FAILURE")
        )
        await session.commit()
        comments = []

        def respond(request):
            if request.url.path == "/repos/owner/app/pulls/7":
                return httpx.Response(200, json=github.pulls[7])
            if request.url.path == "/user":
                return httpx.Response(200, json={"login": "connector-user", "type": "User"})
            if request.url.path.endswith("/comments"):
                if request.method == "POST":
                    comments.append(
                        {
                            "id": 123,
                            "body": json.loads(request.content)["body"],
                            "created_at": datetime.now(UTC).isoformat(),
                        }
                    )
                    return httpx.Response(201, json=comments[-1])
                return httpx.Response(200, json=comments)
            raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

        monkeypatch.setattr(github, "respond", respond)
        root = f"/api/v1/pipeline-runs/{run['id']}"
        resumed = await client.post(f"{root}/resume")
        assert_status_code(resumed, 200)
        assert resumed.json()["state"] == "dispatching"
        advanced = await client.post(f"{root}/advance")
        assert_status_code(advanced, 200)
        assert advanced.json()["state"] == "implementing"
        attempts = (await client.get(f"{root}/attempts")).json()["items"]
        assert len(attempts) == 2
        assert attempts[0]["state"] == "failed"
        assert attempts[0]["failure_code"] == "CI_ENVIRONMENT_FAILURE"
        assert attempts[1]["epoch"] == 2
        assert attempts[1]["idempotency_key"] != attempts[0]["idempotency_key"]
        assert len(comments) == 1

    @pytest.mark.parametrize("state", ["implementing", "awaiting_ci"])
    @pytest.mark.parametrize("merged", [True, False])
    async def test_closed_pull_recovers_actual_merge_outcome(self, client, project, github, session, state, merged):
        run, _ = await prepare_run(client, project)
        await session.execute(update(PipelineRun).where(PipelineRun.id == UUID(run["id"])).values(state=state))
        await session.commit()
        github.pulls[7] = pull(7, state="closed", merged=merged)
        root = f"/api/v1/pipeline-runs/{run['id']}"

        response = await client.post(f"{root}/advance")

        assert_status_code(response, 200)
        assert response.json()["state"] == ("completed" if merged else "canceled")
        attempts = (await client.get(f"{root}/attempts")).json()["items"]
        assert attempts[0]["state"] == ("completed" if merged else "failed")
        assert attempts[0]["finished_at"] is not None
        assert attempts[0]["failure_code"] == (None if merged else "PR_CLOSED")

    async def test_webhook_cannot_deliver_a_quota_retry_early(self, client, project, github, session):
        from unittest.mock import AsyncMock, MagicMock

        from app.features.project_management.github_webhooks.repos import GitHubWebhookRepository
        from app.features.project_management.github_webhooks.usecases import GitHubWebhookUseCase
        from app.features.project_management.pipeline_runs.repos import PipelineRunRepository
        from app.features.project_management.pipeline_runs.usecases.lifecycle import PipelineRunUseCase

        run, _ = await prepare_run(client, project)
        due = datetime.now(UTC) + timedelta(hours=5)
        await session.execute(update(PipelineRun).where(PipelineRun.id == UUID(run["id"])).values(next_action_at=due))
        await session.commit()
        reads = len(github.paths)
        # The deferred dispatch returns before resolving any project or credentials.
        lifecycle = PipelineRunUseCase(PipelineRunRepository(), MagicMock(), MagicMock())
        webhook = GitHubWebhookUseCase(GitHubWebhookRepository(), PipelineRunRepository(), lifecycle)
        webhook._finish = AsyncMock()
        await webhook.process("quota-event", {"repository": {"full_name": "owner/app"}, "issue": {"number": 7}})
        webhook._finish.assert_awaited_once_with("quota-event", "processed")
        detail = await client.get(f"/api/v1/pipeline-runs/{run['id']}")
        assert detail.json()["state"] == "dispatching"
        recorded_due = datetime.fromisoformat(detail.json()["next_action_at"].replace("Z", "+00:00"))
        assert recorded_due.replace(tzinfo=UTC) == due
        assert len(github.paths) == reads
        attempts = (await client.get(f"/api/v1/pipeline-runs/{run['id']}/attempts")).json()["items"]
        deliveries = await client.get(f"/api/v1/pipeline-runs/{run['id']}/attempts/{attempts[0]['id']}/deliveries")
        assert deliveries.json() == []


@pytest.mark.parametrize("excluded", ["paused", "blocked", "future", "leased"])
async def test_ready_batch_filters_before_limit(client, project, github, session, excluded):
    from app.features.project_management.pipeline_runs.repos import PipelineRunRepository

    first = (await enroll(client, project)).json()
    now = datetime.now(UTC)
    values: dict = {"state": excluded} if excluded in ("paused", "blocked") else {}
    if excluded == "future":
        values["next_action_at"] = now + timedelta(hours=5)
    if excluded == "leased":
        values.update(lease_owner="busy-worker", lease_token=uuid4(), lease_expires_at=now + timedelta(minutes=2))
    await session.execute(update(PipelineRun).where(PipelineRun.id == UUID(first["id"])).values(**values))
    await session.commit()
    second = (await enroll(client, project, 8)).json()

    ready = await PipelineRunRepository().list_active(session, UUID(project["id"]), limit=1, ready_at=now)

    assert [str(run.id) for run in ready] == [second["id"]]


async def test_catalog_hold_gates_only_dispatching_runs(client, project, github, session):
    from app.features.ai_catalogs.models import AICatalog, AICatalogState
    from app.features.project_management.pipeline_runs.repos import PipelineRunRepository

    observing = (await enroll(client, project)).json()
    waiting = (await enroll(client, project, 8)).json()
    now = datetime.now(UTC)
    await session.execute(
        update(PipelineRun).where(PipelineRun.id == UUID(observing["id"])).values(state="awaiting_ci")
    )
    await session.execute(update(PipelineRun).where(PipelineRun.id == UUID(waiting["id"])).values(state="dispatching"))
    await session.execute(
        update(AICatalog)
        .where(AICatalog.id == UUID(observing["ai_catalog_id"]))
        .values(availability_state=AICatalogState.QUOTA_BLOCKED, available_at=now + timedelta(hours=5))
    )
    await session.commit()

    ready = await PipelineRunRepository().list_active(session, UUID(project["id"]), limit=10, ready_at=now)

    assert [str(run.id) for run in ready] == [observing["id"]]


async def test_runs_waiting_for_admission_do_not_hold_catalog_capacity(client, project, github, session):
    from app.features.ai_catalogs.repos import AICatalogRepository
    from app.features.project_management.pipeline_runs.models import ExecutionAttempt

    first, attempt = await prepare_run(client, project)
    second = (await enroll(client, project, 8)).json()
    await session.execute(update(PipelineRun).where(PipelineRun.id == UUID(second["id"])).values(state="dispatching"))
    await session.commit()
    catalog_id, repo = UUID(first["ai_catalog_id"]), AICatalogRepository()

    # Two planned dispatches at concurrency 1 must not see each other as capacity holders.
    assert await repo.active_dispatch_count(session, catalog_id, UUID(first["id"])) == 0
    assert await repo.active_dispatch_count(session, catalog_id, UUID(second["id"])) == 0

    await session.execute(
        update(ExecutionAttempt).where(ExecutionAttempt.id == UUID(attempt["id"])).values(state="dispatching")
    )
    await session.commit()

    assert await repo.active_dispatch_count(session, catalog_id, UUID(second["id"])) == 1
    listing = await client.get("/api/v1/ai-catalogs")
    assert [item["active_dispatch_count"] for item in listing.json()["items"]] == [1]


@pytest.mark.parametrize(
    ("run_state", "attempt_state", "in_flight"),
    [("dispatching", "planned", False), ("dispatching", "dispatching", True), ("implementing", "running", True)],
)
async def test_project_change_blocks_a_stuck_run_and_a_settings_only_resume_continues(
    client, project, github, session, run_state, attempt_state, in_flight
):
    from app.features.project_management.pipeline_runs.models import ExecutionAttempt

    run, attempt = await prepare_run(client, project)
    await session.execute(update(PipelineRun).where(PipelineRun.id == UUID(run["id"])).values(state=run_state))
    await session.execute(
        update(ExecutionAttempt).where(ExecutionAttempt.id == UUID(attempt["id"])).values(state=attempt_state)
    )
    await session.execute(
        update(ProjectConnection)
        .where(ProjectConnection.id == UUID(project["id"]))
        .values(revision=ProjectConnection.revision + 1)
    )
    await session.commit()
    reads = len(github.paths)

    response = await client.post(f"/api/v1/pipeline-runs/{run['id']}/advance")

    assert_status_code(response, 200)
    assert response.json()["state"] == "blocked"
    assert response.json()["pause_reason"] == run_usecases.PROJECT_CHANGED_BLOCK_REASON + (
        run_usecases.IN_FLIGHT_RESUME_WARNING if in_flight else ""
    )
    assert len(github.paths) == reads
    attempts = (await client.get(f"/api/v1/pipeline-runs/{run['id']}/attempts")).json()["items"]
    assert attempts[0]["state"] == "failed"
    assert attempts[0]["failure_code"] == "PROJECT_CHANGED"
    catalogs = (await client.get("/api/v1/ai-catalogs")).json()["items"]
    assert [item["active_dispatch_count"] for item in catalogs] == [0]

    # The repository and GitHub connection are unchanged, so a resume adopts the new project revision.
    resumed = await client.post(f"/api/v1/pipeline-runs/{run['id']}/resume")
    assert_status_code(resumed, 200)
    assert resumed.json()["state"] == "dispatching"
    assert resumed.json()["project_revision"] == run["project_revision"] + 1


@pytest.mark.parametrize("changed", ["repository", "connector"])
async def test_resume_requires_enrolling_again_when_the_github_binding_changed(
    client, project, github, session, changed
):
    run, _ = await prepare_run(client, project)
    values: dict = {"revision": ProjectConnection.revision + 1}
    if changed == "repository":
        values["github_repository"] = "owner/other"
    else:
        connector = await client.post(
            "/api/v1/connectors",
            json={"name": "other-account", "provider": "github", "credentials": {"token": "other-token"}},
        )
        assert_status_code(connector, 201)
        values["github_connector_id"] = UUID(connector.json()["id"])
    await session.execute(update(ProjectConnection).where(ProjectConnection.id == UUID(project["id"])).values(**values))
    await session.execute(update(PipelineRun).where(PipelineRun.id == UUID(run["id"])).values(state="blocked"))
    await session.commit()
    reads = len(github.paths)

    response = await client.post(f"/api/v1/pipeline-runs/{run['id']}/resume")

    assert_status_code(response, 409)
    assert response.json()["detail"] == run_usecases.GITHUB_BINDING_CHANGED_CONFLICT
    assert len(github.paths) == reads


@pytest.fixture
def mention_github(github, monkeypatch):
    original = github.respond
    comments = []

    def respond(request):
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "connector-user", "type": "User"})
        if request.url.path.endswith("/comments"):
            if request.method == "POST":
                comments.append(
                    {
                        "id": len(comments) + 100,
                        "body": json.loads(request.content)["body"],
                        "created_at": datetime.now(UTC).isoformat(),
                        "user": {"login": "connector-user"},
                    }
                )
                return httpx.Response(201, json=comments[-1])
            return httpx.Response(200, json=comments)
        return original(request)

    monkeypatch.setattr(github, "respond", respond)
    return comments


async def test_resume_requires_a_new_push_and_preserves_previous_request(client, project, github, mention_github):
    run, original = await prepare_run(client, project)
    root = f"/api/v1/pipeline-runs/{run['id']}"
    assert_status_code(await client.post(f"{root}/advance"), 200)
    github.pulls[7]["head"]["sha"] = "e" * 40
    assert (await client.post(f"{root}/advance")).json()["state"] == "awaiting_ci"
    assert_status_code(await client.post(f"{root}/pause"), 200)

    resumed = await client.post(f"{root}/resume")
    assert_status_code(resumed, 200)
    assert resumed.json()["state"] == "dispatching"
    assert (await client.post(f"{root}/advance")).json()["state"] == "implementing"
    assert (await client.post(f"{root}/advance")).json()["state"] == "implementing"
    attempts = (await client.get(f"{root}/attempts")).json()["items"]
    assert len(attempts) == 2
    assert attempts[0]["request_snapshot"] == original["request_snapshot"]
    assert attempts[0]["state"] == "failed"
    assert attempts[1]["request_snapshot"]["pull_request"]["head_sha"] == "e" * 40
    assert attempts[1]["idempotency_key"] != original["idempotency_key"]
    canonical = json.dumps(attempts[1]["request_snapshot"], sort_keys=True, separators=(",", ":"))
    assert attempts[1]["request_digest"] == sha256(canonical.encode()).hexdigest()
    deliveries = (await client.get(f"{root}/attempts/{attempts[1]['id']}/deliveries")).json()
    assert deliveries[0]["cause"] == "resume"
    assert f"head={'e' * 40}" in mention_github[-1]["body"]

    github.pulls[7]["head"]["sha"] = "f" * 40
    assert (await client.post(f"{root}/advance")).json()["state"] == "awaiting_ci"


async def test_reconciled_delivery_preserves_time_and_processes_existing_quota_reply(client, project, mention_github):
    from app.features.project_management.pipeline_runs.dispatch import build_codex_mention_comment
    from app.features.project_management.pipeline_runs.schemas import ImplementationRequest

    run, attempt = await prepare_run(client, project)
    root = f"/api/v1/pipeline-runs/{run['id']}"
    posted_at = datetime.now(UTC) - timedelta(hours=5)
    replied_at = posted_at + timedelta(minutes=1)
    mention_github.extend(
        [
            {
                "id": 77,
                "body": build_codex_mention_comment(ImplementationRequest.model_validate(attempt["request_snapshot"])),
                "created_at": posted_at.isoformat(),
                "user": {"login": "connector-user"},
            },
            {
                "id": 78,
                "body": "You reached a Codex usage limit.",
                "created_at": replied_at.isoformat(),
                "user": {"login": "chatgpt-codex-connector"},
            },
        ]
    )
    assert_status_code(await client.post(f"{root}/advance"), 200)
    deliveries = (await client.get(f"{root}/attempts/{attempt['id']}/deliveries")).json()
    stored_time = datetime.fromisoformat(deliveries[0]["posted_at"].replace("Z", "+00:00")).replace(tzinfo=UTC)
    assert stored_time == posted_at
    assert deliveries[0]["comment_id"] == "77"

    response = await client.post(f"{root}/advance")
    assert_status_code(response, 200)
    assert response.json()["state"] == "dispatching"
    assert response.json()["next_action_at"] is None
    catalogs = (await client.get("/api/v1/ai-catalogs")).json()["items"]
    catalog = next(item for item in catalogs if item["key"] == "personal-codex")
    due = datetime.fromisoformat(catalog["available_at"].replace("Z", "+00:00")).replace(tzinfo=UTC)
    # The reconciled mention is the first task of the usage window, so the wait starts from it.
    assert due == posted_at + timedelta(hours=5, minutes=10)
    replies = (await client.get(f"{root}/attempts/{attempt['id']}/replies")).json()
    assert len(replies) == 1 and replies[0]["is_quota_limit"] is True
    assert len(mention_github) == 2


async def test_probe_window_starts_when_the_probe_mention_is_delivered(client, project, mention_github, session):
    from app.features.ai_catalogs.models import AICatalog, AICatalogState

    run, _ = await prepare_run(client, project)
    await session.execute(
        update(AICatalog)
        .where(AICatalog.id == UUID(run["ai_catalog_id"]))
        .values(availability_state=AICatalogState.QUOTA_BLOCKED, available_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await session.commit()

    response = await client.post(f"/api/v1/pipeline-runs/{run['id']}/advance")

    assert_status_code(response, 200)
    assert response.json()["state"] == "implementing"
    catalog = (await client.get("/api/v1/ai-catalogs")).json()["items"][0]
    assert catalog["availability_state"] == "probe"
    assert catalog["effective_concurrency"] == 1
    probe_started_at = datetime.fromisoformat(catalog["probe_started_at"].replace("Z", "+00:00")).replace(tzinfo=UTC)
    assert probe_started_at == datetime.fromisoformat(mention_github[0]["created_at"])


async def test_a_retried_delivery_is_counted_once_in_the_catalog_ledger(
    client, project, mention_github, session, monkeypatch
):
    import asyncio

    from app.features.ai_catalogs.models import AICatalogDispatch
    from app.features.project_management.pipelines.github import GitHubActionsReader
    from sqlalchemy import select

    run, attempt = await prepare_run(client, project)
    root = f"/api/v1/pipeline-runs/{run['id']}"

    async def stall(*args):
        await asyncio.Event().wait()

    with monkeypatch.context() as patched:
        patched.setattr(run_usecases, "DISPATCH_IO_SECONDS", 0.05)
        patched.setattr(GitHubActionsReader, "reconcile_issue_comment", stall)
        assert_status_code(await client.post(f"{root}/advance"), 504)
    assert (await client.post(f"{root}/advance")).json()["state"] == "implementing"

    deliveries = (await client.get(f"{root}/attempts/{attempt['id']}/deliveries")).json()
    ledger = (await session.scalars(select(AICatalogDispatch))).all()
    assert [entry.dispatch_key for entry in ledger] == [f"delivery:{deliveries[0]['id']}"]


async def test_expired_dispatcher_cannot_post_after_another_worker_takes_over(
    client, project, mention_github, session, monkeypatch
):
    import asyncio

    from app.features.project_management.pipelines.github import GitHubActionsReader

    run, attempt = await prepare_run(client, project)
    root = f"/api/v1/pipeline-runs/{run['id']}"
    original = GitHubActionsReader.reconcile_issue_comment
    observed_absent, allow_old_response = asyncio.Event(), asyncio.Event()
    reads = 0

    async def delayed_reconcile(reader, *args):
        nonlocal reads
        reads += 1
        result = await original(reader, *args)
        if reads == 1:
            observed_absent.set()
            await allow_old_response.wait()
        return result

    monkeypatch.setattr(GitHubActionsReader, "reconcile_issue_comment", delayed_reconcile)
    first = asyncio.create_task(client.post(f"{root}/advance"))
    try:
        await asyncio.wait_for(observed_absent.wait(), timeout=5)
        await session.execute(
            update(PipelineRun)
            .where(PipelineRun.id == UUID(run["id"]))
            .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
        second = await client.post(f"{root}/advance")
        assert_status_code(second, 200)
        assert second.json()["state"] == "implementing"
    finally:
        allow_old_response.set()
    rejected = await first
    assert_status_code(rejected, 409)
    assert len(mention_github) == 1
    deliveries = (await client.get(f"{root}/attempts/{attempt['id']}/deliveries")).json()
    assert len(deliveries) == 1
    assert deliveries[0]["comment_id"] == str(mention_github[0]["id"])


async def test_delivery_timeout_leaves_one_reconcilable_delivery(client, project, mention_github, monkeypatch):
    import asyncio

    from app.features.project_management.pipelines.github import GitHubActionsReader

    run, attempt = await prepare_run(client, project)
    root = f"/api/v1/pipeline-runs/{run['id']}"

    async def stall(*args):
        await asyncio.Event().wait()

    with monkeypatch.context() as patched:
        patched.setattr(run_usecases, "DISPATCH_IO_SECONDS", 0.05)
        patched.setattr(GitHubActionsReader, "reconcile_issue_comment", stall)
        response = await client.post(f"{root}/advance")
    assert_status_code(response, 504)
    assert mention_github == []
    assert_status_code(await client.post(f"{root}/advance"), 200)
    deliveries = (await client.get(f"{root}/attempts/{attempt['id']}/deliveries")).json()
    assert len(deliveries) == 1
    assert len(mention_github) == 1


async def test_post_response_crash_is_reconciled_without_a_duplicate_mention(
    client, project, mention_github, monkeypatch
):
    """A crash after GitHub accepts the comment must be safe to retry.

    The first advance loses the process immediately before it can persist the
    accepted response.  The retry must discover the connector-authored marker
    and adopt it instead of posting a second mention.
    """
    from app.features.project_management.pipeline_runs.repos import PipelineRunRepository

    run, attempt = await prepare_run(client, project)
    root = f"/api/v1/pipeline-runs/{run['id']}"
    original_get_leased = PipelineRunRepository.get_leased
    calls = 0

    async def crash_before_recording(self, session, run_id, *, owner, token, now):
        nonlocal calls
        calls += 1
        # dispatch setup, its two authorization guards, then the transaction
        # that records GitHub's already-accepted response.
        if calls == 4:
            raise RuntimeError("simulated process crash after GitHub POST")
        return await original_get_leased(self, session, run_id, owner=owner, token=token, now=now)

    with monkeypatch.context() as patched:
        patched.setattr(PipelineRunRepository, "get_leased", crash_before_recording)
        with pytest.raises(RuntimeError, match="simulated process crash"):
            await client.post(f"{root}/advance")

    assert len(mention_github) == 1

    recovered = await client.post(f"{root}/advance")

    assert_status_code(recovered, 200)
    assert recovered.json()["state"] == "implementing"
    assert len(mention_github) == 1
    deliveries = await client.get(f"{root}/attempts/{attempt['id']}/deliveries")
    assert len(deliveries.json()) == 1
    assert deliveries.json()[0]["comment_id"] == str(mention_github[0]["id"])


async def test_pre_post_crash_reuses_the_planned_delivery_on_restart(client, project, mention_github, monkeypatch):
    """A crash before GitHub I/O leaves one durable delivery to retry."""
    from app.features.project_management.pipeline_runs.usecases.lifecycle import PipelineRunUseCase

    run, attempt = await prepare_run(client, project)
    root = f"/api/v1/pipeline-runs/{run['id']}"
    original_guard = PipelineRunUseCase._guard_dispatch
    guards = 0

    async def crash_before_post(self, *args, **kwargs):
        nonlocal guards
        guards += 1
        if guards == 1:
            raise RuntimeError("simulated process crash before GitHub POST")
        return await original_guard(self, *args, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(PipelineRunUseCase, "_guard_dispatch", crash_before_post)
        with pytest.raises(RuntimeError, match="simulated process crash"):
            await client.post(f"{root}/advance")

    assert mention_github == []
    deliveries = await client.get(f"{root}/attempts/{attempt['id']}/deliveries")
    assert len(deliveries.json()) == 1
    assert deliveries.json()[0]["comment_id"] is None

    recovered = await client.post(f"{root}/advance")
    assert_status_code(recovered, 200)
    assert recovered.json()["state"] == "implementing"
    assert len(mention_github) == 1


async def test_push_transition_crash_is_recovered_from_the_new_head(
    client, project, github, mention_github, monkeypatch
):
    """A restart after a push read repeats the transition without another mention."""
    from sqlalchemy.ext.asyncio import AsyncSession

    run, attempt = await prepare_run(client, project)
    root = f"/api/v1/pipeline-runs/{run['id']}"
    assert (await client.post(f"{root}/advance")).json()["state"] == "implementing"
    github.pulls[7]["head"]["sha"] = "e" * 40
    original_flush = AsyncSession.flush

    async def crash_before_persisting_head(self, *args, **kwargs):
        if any(
            isinstance(item, PipelineRun) and item.state == PipelineRunState.AWAITING_CI
            for item in self.identity_map.values()
        ):
            raise RuntimeError("simulated process crash after push read")
        return await original_flush(self, *args, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(AsyncSession, "flush", crash_before_persisting_head)
        with pytest.raises(RuntimeError, match="simulated process crash"):
            await client.post(f"{root}/advance")

    assert (await client.get(root)).json()["state"] == "implementing"
    recovered = await client.post(f"{root}/advance")
    assert_status_code(recovered, 200)
    assert recovered.json()["state"] == "awaiting_ci"
    assert len(mention_github) == 1
    deliveries = await client.get(f"{root}/attempts/{attempt['id']}/deliveries")
    assert len(deliveries.json()) == 1


@pytest.mark.parametrize("invalid_time", [None, "not-a-timestamp"])
async def test_invalid_comment_time_is_not_replaced_by_recovery_time(client, project, mention_github, invalid_time):
    from app.features.project_management.pipeline_runs.dispatch import build_codex_mention_comment
    from app.features.project_management.pipeline_runs.schemas import ImplementationRequest

    run, attempt = await prepare_run(client, project)
    root = f"/api/v1/pipeline-runs/{run['id']}"
    mention_github.append(
        {
            "id": 77,
            "body": build_codex_mention_comment(ImplementationRequest.model_validate(attempt["request_snapshot"])),
            "created_at": invalid_time,
            "user": {"login": "connector-user"},
        }
    )
    for _ in range(2):
        assert_status_code(await client.post(f"{root}/advance"), 502)
    assert len(mention_github) == 1
    deliveries = (await client.get(f"{root}/attempts/{attempt['id']}/deliveries")).json()
    assert deliveries[0]["posted_at"] is None
