from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from app.features import tasks
from app.features.pipelines import services
from app.features.schedule_configs.models import ScheduleConfig
from app.features.schedule_jobs.models import ScheduleJob
from app.features.tasks.domains.pipeline import task as pipeline_task
from sqlalchemy import select, update
from tests.utils.assertions import assert_status_code

pytestmark = [pytest.mark.e2e, pytest.mark.real_commit]
HEAD = "a" * 40


class GitHubScenario:
    """HTTP boundary fixture: all application layers and credential encryption remain real."""

    def __init__(self):
        self.pr = {
            "number": 42,
            "state": "open",
            "head": {"sha": HEAD, "repo": {"full_name": "owner/app"}},
            "base": {"sha": "b" * 40},
            "html_url": "https://github.com/owner/app/pull/42",
        }
        self.runs = [
            {
                "id": 10,
                "run_number": 1,
                "run_attempt": 1,
                "head_sha": HEAD,
                "event": "pull_request",
                "path": ".github/workflows/ci.yml",
                "head_repository": {"full_name": "owner/app"},
                "pull_requests": [{"number": 42, "head": {"sha": HEAD}}],
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://github.com/owner/app/actions/runs/10",
                "updated_at": "2026-09-10T00:00:00Z",
            }
        ]
        self.jobs = [{"name": name, "status": "completed", "conclusion": "success"} for name in ("lint", "test")]
        self.requests: list[httpx.Request] = []
        self.error_status: int | None = None
        self.change_pr = False
        self.change_attempt = False
        self.invalid_response = False

    def respond(self, request: httpx.Request) -> httpx.Response:
        assert request.method == "GET", "The observer must never mutate GitHub"
        self.requests.append(request)
        if self.error_status:
            return httpx.Response(self.error_status, json={"message": "upstream-sensitive-body"})
        if self.invalid_response:
            return httpx.Response(200, json={"unexpected": True})
        path = request.url.path
        if path == "/repos/owner/app/pulls/42":
            pr = deepcopy(self.pr)
            count = sum(r.url.path == path for r in self.requests)
            if self.change_pr and count > 1:
                pr["head"]["sha"] = "c" * 40
            return httpx.Response(200, json=pr)
        if path == "/repos/owner/app/actions/workflows/ci.yml/runs":
            assert request.url.params["head_sha"] == HEAD
            assert request.url.params["event"] == "pull_request"
            page = int(request.url.params["page"])
            return httpx.Response(200, json={"workflow_runs": self.runs[(page - 1) * 100 : page * 100]})
        if path.endswith("/jobs"):
            assert request.url.params["filter"] == "latest"
            page = int(request.url.params["page"])
            return httpx.Response(200, json={"jobs": self.jobs[(page - 1) * 100 : page * 100]})
        if "/actions/runs/" in path:
            run = deepcopy(next(run for run in self.runs if run["id"] == int(path.rsplit("/", 1)[1])))
            if self.change_attempt:
                run["run_attempt"] += 1
            return httpx.Response(200, json=run)
        raise AssertionError(f"Unexpected GitHub request: {path}")


@pytest.fixture
def github_scenario(monkeypatch, credential_key_provider):
    scenario = GitHubScenario()

    def create_client(token):
        assert token == "github-test-token"
        return httpx.AsyncClient(base_url="https://api.github.com", transport=httpx.MockTransport(scenario.respond))

    monkeypatch.setattr(services, "create_github_client", create_client)
    monkeypatch.setattr(pipeline_task, "get_credential_key_provider", lambda: credential_key_provider)
    tasks.autodiscover()
    return scenario


@pytest.fixture
async def observation_payload(client, github_scenario):
    response = await client.post(
        "/api/v1/connectors",
        json={"name": "github-observer", "provider": "github", "credentials": {"token": "github-test-token"}},
    )
    assert_status_code(response, 201)
    return {
        "repository": "owner/app",
        "linear_project_id": str(uuid4()),
        "github_connector_id": response.json()["id"],
        "pull_numbers": [42],
        "verification": {"workflow": "ci.yml", "required_jobs": ["lint", "test"]},
    }


class TestPipelineObservationAPI:
    async def test_inspect_reads_github_without_persisting_or_exposing_token(
        self, client, observation_payload, session
    ):
        from app.features.task_states.models import TaskState

        response = await client.post("/api/v1/pipelines/inspect", json=observation_payload)
        assert_status_code(response, 200)
        assert response.json()["pulls"][0]["result"]["status"] == "passed"
        assert response.json()["pulls"][0]["run"]["id"] == 10
        assert "github-test-token" not in response.text
        assert not (await session.execute(select(TaskState))).scalars().all()

    @pytest.mark.parametrize("field", ["head_sha", "event", "path", "pull_requests", "head_repository"])
    async def test_unrelated_run_never_passes(self, client, observation_payload, github_scenario, field):
        github_scenario.runs[0][field] = {
            "head_sha": "c" * 40,
            "event": "push",
            "path": ".github/workflows/docs.yml",
            "pull_requests": [{"number": 99, "head": {"sha": HEAD}}],
            "head_repository": {"full_name": "someone/fork"},
        }[field]
        response = await client.post("/api/v1/pipelines/inspect", json=observation_payload)
        assert_status_code(response, 200)
        assert response.json()["pulls"][0]["result"]["status"] == "waiting"

    async def test_latest_pending_run_supersedes_previous_success(self, client, observation_payload, github_scenario):
        new_run = {**github_scenario.runs[0], "id": 11, "run_number": 2, "status": "queued", "conclusion": None}
        github_scenario.runs.append(new_run)
        response = await client.post("/api/v1/pipelines/inspect", json=observation_payload)
        assert_status_code(response, 200)
        pull = response.json()["pulls"][0]
        assert pull["run"]["id"] == 11
        assert pull["result"]["status"] == "waiting"

    @pytest.mark.parametrize("change", ["change_pr", "change_attempt"])
    async def test_concurrent_changes_invalidate_success(self, client, observation_payload, github_scenario, change):
        setattr(github_scenario, change, True)
        response = await client.post("/api/v1/pipelines/inspect", json=observation_payload)
        assert_status_code(response, 200)
        assert response.json()["pulls"][0]["result"]["status"] == "waiting"

    async def test_jobs_are_paginated_before_decision(self, client, observation_payload, github_scenario):
        github_scenario.jobs = [
            {"name": f"optional-{i}", "status": "completed", "conclusion": "success"} for i in range(100)
        ] + github_scenario.jobs
        response = await client.post("/api/v1/pipelines/inspect", json=observation_payload)
        assert_status_code(response, 200)
        assert response.json()["pulls"][0]["result"]["status"] == "passed"
        assert any(r.url.params.get("page") == "2" for r in github_scenario.requests)

    async def test_closed_and_fork_pulls_do_not_query_actions(self, client, observation_payload, github_scenario):
        github_scenario.pr["state"] = "closed"
        response = await client.post("/api/v1/pipelines/inspect", json=observation_payload)
        assert response.json()["pulls"][0]["result"]["status"] == "closed"
        github_scenario.pr["state"] = "open"
        github_scenario.pr["head"]["repo"]["full_name"] = "someone/fork"
        response = await client.post("/api/v1/pipelines/inspect", json=observation_payload)
        assert response.json()["pulls"][0]["result"]["status"] == "blocked"
        assert len(github_scenario.requests) == 2

    @pytest.mark.parametrize("code", [403, 404, 429, 500])
    async def test_upstream_errors_are_sanitized(self, client, observation_payload, github_scenario, code):
        github_scenario.error_status = code
        response = await client.post("/api/v1/pipelines/inspect", json=observation_payload)
        assert_status_code(response, 502)
        assert "upstream-sensitive-body" not in response.text
        assert "github-test-token" not in response.text

    async def test_malformed_upstream_data_is_not_success(self, client, observation_payload, github_scenario):
        github_scenario.invalid_response = True
        response = await client.post("/api/v1/pipelines/inspect", json=observation_payload)
        assert_status_code(response, 502)

    @pytest.mark.parametrize("jobs", [[], ["lint", "lint"]])
    async def test_empty_or_duplicate_contract_is_rejected(self, client, observation_payload, github_scenario, jobs):
        observation_payload["verification"]["required_jobs"] = jobs
        response = await client.post("/api/v1/pipelines/inspect", json=observation_payload)
        assert_status_code(response, 422)
        assert not github_scenario.requests

    async def test_disabled_connector_is_rejected_before_network(self, client, observation_payload, github_scenario):
        response = await client.patch(
            f"/api/v1/connectors/{observation_payload['github_connector_id']}", json={"enabled": False}
        )
        assert_status_code(response, 200)
        response = await client.post("/api/v1/pipelines/inspect", json=observation_payload)
        assert_status_code(response, 422)
        assert not github_scenario.requests

    async def test_schedule_dispatch_persists_report_and_distinguishes_ci_failure(
        self, client, observation_payload, github_scenario, session
    ):
        response = await client.post(
            "/api/v1/schedule_configs",
            json={
                "name": "observe-app",
                "task_func": "pipeline.observe",
                "interval_seconds": 300,
                "payload": observation_payload,
            },
        )
        assert_status_code(response, 201)
        schedule_id = response.json()["id"]
        # Creation schedules the first future tick; advance its due time without waiting for wall time.
        await session.execute(
            update(ScheduleConfig)
            .where(ScheduleConfig.id == UUID(schedule_id))
            .values(next_run_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
        response = await client.get(f"/api/v1/pipelines/observations/{schedule_id}")
        assert_status_code(response, 404)

        github_scenario.runs[0]["conclusion"] = "failure"
        response = await client.post("/api/v1/dispatchers/trigger")
        assert_status_code(response, 200)
        assert response.json()["dispatched"] == 1
        response = await client.get(f"/api/v1/pipelines/observations/{schedule_id}")
        assert_status_code(response, 200)
        assert response.json()["pulls"][0]["result"]["status"] == "failed"
        assert response.json()["config"]["repository"] == "owner/app"
        job = (await session.execute(select(ScheduleJob))).scalar_one()
        assert job.status == "success"

        # A failed observation leaves the last report intact and fails the scheduler job.
        previous_report = response.json()
        github_scenario.error_status = 503
        await session.execute(
            update(ScheduleConfig)
            .where(ScheduleConfig.id == UUID(schedule_id))
            .values(next_run_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
        response = await client.post("/api/v1/dispatchers/trigger")
        assert_status_code(response, 200)
        response = await client.get(f"/api/v1/pipelines/observations/{schedule_id}")
        assert_status_code(response, 200)
        assert response.json() == previous_report
        session.expire_all()
        jobs = (await session.execute(select(ScheduleJob))).scalars().all()
        assert sorted(job.status for job in jobs) == ["failure", "success"]

        # A changed configuration must not show the old configuration's report.
        observation_payload["pull_numbers"] = [43]
        response = await client.patch(f"/api/v1/schedule_configs/{schedule_id}", json={"payload": observation_payload})
        assert_status_code(response, 200)
        response = await client.get(f"/api/v1/pipelines/observations/{schedule_id}")
        assert_status_code(response, 404)

    async def test_observer_is_exposed_in_task_specs(self, client, github_scenario):
        from app.features.tasks.usecases.task_spec import GetTaskSpecUseCase

        GetTaskSpecUseCase.clear_cache()
        response = await client.get("/api/v1/tasks/specs?name=pipeline.observe")
        assert_status_code(response, 200)
        assert response.json()[0]["payload_schema"]["title"] == "PipelineObservationConfig"
