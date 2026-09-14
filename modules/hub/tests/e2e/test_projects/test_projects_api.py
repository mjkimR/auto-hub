from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from app.features import tasks
from app.features.execution.tasks.domains.pipeline import task as pipeline_task
from app.features.project_management.pipelines import services
from app.features.scheduling.schedule_configs.models import ScheduleConfig
from app.features.scheduling.schedule_jobs.models import ScheduleJob
from sqlalchemy import select, update
from tests.utils.assertions import assert_status_code

pytestmark = [pytest.mark.e2e, pytest.mark.real_commit]
HEAD = "a" * 40
VERIFICATION = {"workflow": "ci.yml", "required_jobs": ["lint", "test"], "event": "pull_request"}


class GitHubScenario:
    """HTTP boundary fixture: routers, services, repositories and credential encryption stay real."""

    def __init__(self):
        self.repository = {"full_name": "owner/app", "archived": False}
        self.workflow = {"id": 1, "name": "CI", "state": "active", "path": ".github/workflows/ci.yml"}
        self.user = {"login": "owner", "type": "User"}
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
                "pull_requests": [{"number": 42, "head": {"sha": HEAD}, "base": {"sha": "b" * 40}}],
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://github.com/owner/app/actions/runs/10",
                "updated_at": "2026-09-10T00:00:00Z",
            }
        ]
        self.jobs = [{"name": name, "status": "completed", "conclusion": "success"} for name in ("lint", "test")]
        self.requests: list[httpx.Request] = []
        self.failures: dict[str, int] = {}

    def respond(self, request: httpx.Request) -> httpx.Response:
        assert request.method == "GET", "Connection checks and observations must never mutate GitHub"
        self.requests.append(request)
        path = request.url.path
        if path in self.failures:
            return httpx.Response(self.failures[path], json={"message": "upstream-sensitive-body"})
        if path == "/user":
            return httpx.Response(200, json=self.user)
        if path == "/repos/owner/app":
            return httpx.Response(200, json=self.repository)
        if path == "/repos/owner/app/actions/workflows/ci.yml":
            return httpx.Response(200, json=self.workflow)
        if path == "/repos/owner/app/pulls/42":
            return httpx.Response(200, json=deepcopy(self.pr))
        if path == "/repos/owner/app/actions/workflows/ci.yml/runs":
            page = int(request.url.params["page"])
            return httpx.Response(200, json={"workflow_runs": self.runs[(page - 1) * 100 : page * 100]})
        if path.endswith("/jobs"):
            page = int(request.url.params["page"])
            return httpx.Response(200, json={"jobs": self.jobs[(page - 1) * 100 : page * 100]})
        if "/actions/runs/" in path:
            return httpx.Response(200, json=deepcopy(next(run for run in self.runs if run["id"] == 10)))
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
async def github_connector(client, github_scenario) -> str:
    response = await client.post(
        "/api/v1/connectors",
        json={"name": "github-account", "provider": "github", "credentials": {"token": "github-test-token"}},
    )
    assert_status_code(response, 201)
    return response.json()["id"]


@pytest.fixture
def project_payload(github_connector) -> dict:
    return {
        "name": "Application",
        "repository": "owner/app",
        "github_connector_id": github_connector,
        "verification": VERIFICATION,
    }


@pytest.fixture
async def project(client, project_payload) -> dict:
    response = await client.post("/api/v1/projects", json=project_payload)
    assert_status_code(response, 201)
    return response.json()


async def make_due(session, schedule_id: str) -> None:
    """Advance the schedule's due time instead of waiting for wall-clock time."""
    await session.execute(
        update(ScheduleConfig)
        .where(ScheduleConfig.id == UUID(schedule_id))
        .values(next_run_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await session.commit()


class TestProjectRegistration:
    async def test_repository_is_stored_normalized_and_never_exposes_credentials(self, client, project_payload):
        project_payload["repository"] = "Owner/App"
        response = await client.post("/api/v1/projects", json=project_payload)
        assert_status_code(response, 201)
        assert response.json()["repository"] == "owner/app"
        assert response.json()["revision"] == 1
        assert response.json()["last_check"] is None
        assert "github-test-token" not in response.text

    async def test_one_repository_maps_to_one_project(self, client, project, project_payload):
        response = await client.post("/api/v1/projects", json={**project_payload, "name": "Duplicate"})
        assert_status_code(response, 409)
        assert response.json()["detail"] == "Repository is already connected"

    async def test_case_only_repository_variants_are_the_same_mapping(self, client, project, project_payload):
        response = await client.post("/api/v1/projects", json={**project_payload, "repository": "OWNER/APP"})
        assert_status_code(response, 409)

    async def test_the_github_connector_must_be_enabled(self, client, project_payload, github_connector):
        assert_status_code(await client.patch(f"/api/v1/connectors/{github_connector}", json={"enabled": False}), 200)
        assert_status_code(await client.post("/api/v1/projects", json=project_payload), 422)

    async def test_missing_connector_is_rejected_without_creating_a_project(self, client, project_payload):
        response = await client.post("/api/v1/projects", json={**project_payload, "github_connector_id": str(uuid4())})
        assert_status_code(response, 422)
        assert (await client.get("/api/v1/projects")).json()["total_count"] == 0

    @pytest.mark.parametrize(
        "verification",
        [
            {"workflow": "ci", "required_jobs": ["lint"]},
            {"workflow": "ci.yml", "required_jobs": []},
            {"workflow": "ci.yml", "required_jobs": ["lint", "lint"]},
            {"workflow": "ci.yml", "required_jobs": [" "]},
        ],
    )
    async def test_required_job_contract_is_validated_at_registration(self, client, project_payload, verification):
        response = await client.post("/api/v1/projects", json={**project_payload, "verification": verification})
        assert_status_code(response, 422)

    async def test_edits_require_the_revision_the_editor_loaded(self, client, project, project_payload):
        stale = {**project_payload, "expected_revision": project["revision"] + 1}
        assert_status_code(await client.put(f"/api/v1/projects/{project['id']}", json=stale), 409)

        current = {**project_payload, "name": "Renamed", "expected_revision": project["revision"]}
        response = await client.put(f"/api/v1/projects/{project['id']}", json=current)
        assert_status_code(response, 200)
        assert response.json()["name"] == "Renamed"
        assert response.json()["revision"] == project["revision"] + 1
        assert_status_code(await client.put(f"/api/v1/projects/{project['id']}", json=current), 409)

    async def test_unknown_project_is_not_found(self, client, github_scenario):
        assert_status_code(await client.get(f"/api/v1/projects/{uuid4()}"), 404)


class TestProjectDeletion:
    async def test_observation_schedules_must_be_removed_first(self, client, project, session):
        response = await client.post(
            "/api/v1/schedule_configs",
            json={
                "name": "observe-app",
                "task_func": "pipeline.observe_project",
                "interval_seconds": 300,
                "payload": {"project_id": project["id"], "pull_numbers": [42]},
            },
        )
        assert_status_code(response, 201)
        schedule_id = response.json()["id"]

        assert_status_code(await client.delete(f"/api/v1/projects/{project['id']}"), 409)
        assert_status_code(await client.get(f"/api/v1/projects/{project['id']}"), 200)

        assert_status_code(await client.delete(f"/api/v1/schedule_configs/{schedule_id}"), 200)
        assert_status_code(await client.delete(f"/api/v1/projects/{project['id']}"), 204)
        assert_status_code(await client.get(f"/api/v1/projects/{project['id']}"), 404)


class TestConnectionCheck:
    async def test_successful_check_is_stored_and_reports_one_verification_run(self, client, project, github_scenario):
        response = await client.post(f"/api/v1/projects/{project['id']}/check", json={"pull_number": 42})
        assert_status_code(response, 200)
        report = response.json()
        assert report["ready"] is True
        assert [check["name"] for check in report["checks"]] == ["GitHub access", "PR verification", "GitHub identity"]
        assert [check["status"] for check in report["checks"]] == ["passed", "passed", "passed"]
        assert report["github_login"] == "owner"
        assert report["observation"]["pulls"][0]["result"]["status"] == "passed"
        assert report["observation"]["pulls"][0]["run"]["url"].startswith("https://github.com/")
        assert report["project_revision"] == project["revision"]

        stored = await client.get(f"/api/v1/projects/{project['id']}")
        assert stored.json()["last_check"]["ready"] is True
        assert stored.json()["last_check"]["github_login"] == "owner"
        assert "github-test-token" not in stored.text

    async def test_a_failing_workflow_is_reported_without_failing_the_request(self, client, project, github_scenario):
        github_scenario.runs[0]["conclusion"] = "failure"
        github_scenario.jobs = [
            {"name": "lint", "status": "completed", "conclusion": "failure"},
            {"name": "test", "status": "completed", "conclusion": "success"},
        ]
        response = await client.post(f"/api/v1/projects/{project['id']}/check", json={"pull_number": 42})
        assert_status_code(response, 200)
        report = response.json()
        assert report["ready"] is False
        assert report["observation"]["pulls"][0]["result"]["status"] == "failed"
        assert report["observation"]["pulls"][0]["result"]["unsuccessful_jobs"] == ["lint"]
        assert [check["status"] for check in report["checks"]] == ["passed", "failed", "passed"]

    async def test_a_required_job_the_workflow_never_runs_does_not_pass(self, client, project, github_scenario):
        """The configured job names are the contract, not whatever the workflow happens to report."""
        github_scenario.jobs = [{"name": "lint", "status": "completed", "conclusion": "success"}]
        response = await client.post(f"/api/v1/projects/{project['id']}/check", json={"pull_number": 42})
        assert_status_code(response, 200)
        result = response.json()["observation"]["pulls"][0]["result"]
        assert result["status"] == "blocked"
        assert result["missing_jobs"] == ["test"]
        assert response.json()["ready"] is False

    @pytest.mark.parametrize(
        ("attribute", "value"),
        [("repository", {"full_name": "owner/app", "archived": True}), ("workflow", {"state": "disabled_manually"})],
    )
    async def test_archived_repositories_and_inactive_workflows_are_reported(
        self, client, project, github_scenario, attribute, value
    ):
        setattr(github_scenario, attribute, {**getattr(github_scenario, attribute), **value})
        response = await client.post(f"/api/v1/projects/{project['id']}/check", json={"pull_number": 42})
        assert_status_code(response, 200)
        assert response.json()["ready"] is False
        assert any(check["status"] == "failed" for check in response.json()["checks"])

    async def test_missing_workflow_file_is_reported_before_observation(self, client, project, github_scenario):
        github_scenario.failures["/repos/owner/app/actions/workflows/ci.yml"] = 404
        response = await client.post(f"/api/v1/projects/{project['id']}/check", json={"pull_number": 42})
        assert_status_code(response, 200)
        assert response.json()["observation"] is None
        assert response.json()["ready"] is False
        assert "upstream-sensitive-body" not in response.text

    async def test_a_non_user_token_cannot_post_codex_mentions(self, client, project, github_scenario):
        github_scenario.user = {"login": "hub-app[bot]", "type": "Bot"}
        response = await client.post(f"/api/v1/projects/{project['id']}/check", json={"pull_number": 42})
        assert_status_code(response, 200)
        checks = {check["name"]: check["status"] for check in response.json()["checks"]}
        assert checks["GitHub access"] == "passed"
        assert checks["GitHub identity"] == "failed"
        assert response.json()["github_login"] is None
        assert response.json()["ready"] is False

    async def test_identity_failure_does_not_hide_a_healthy_ci_connection(self, client, project, github_scenario):
        github_scenario.failures["/user"] = 403
        response = await client.post(f"/api/v1/projects/{project['id']}/check", json={"pull_number": 42})
        assert_status_code(response, 200)
        checks = {check["name"]: check["status"] for check in response.json()["checks"]}
        assert checks["PR verification"] == "passed"
        assert checks["GitHub identity"] == "failed"
        assert response.json()["ready"] is False
        assert "upstream-sensitive-body" not in response.text

    async def test_editing_a_project_discards_its_previous_check(self, client, project, project_payload):
        assert_status_code(await client.post(f"/api/v1/projects/{project['id']}/check", json={"pull_number": 42}), 200)
        response = await client.put(
            f"/api/v1/projects/{project['id']}",
            json={**project_payload, "name": "Renamed", "expected_revision": project["revision"]},
        )
        assert_status_code(response, 200)
        assert response.json()["last_check"] is None


class TestScheduledProjectObservation:
    async def test_schedule_resolves_the_saved_connection_at_run_time(self, client, project, github_scenario, session):
        response = await client.post(
            "/api/v1/schedule_configs",
            json={
                "name": "observe-app",
                "task_func": "pipeline.observe_project",
                "interval_seconds": 300,
                "payload": {"project_id": project["id"], "pull_numbers": [42]},
            },
        )
        assert_status_code(response, 201)
        schedule_id = response.json()["id"]
        await make_due(session, schedule_id)

        assert_status_code(await client.post("/api/v1/dispatchers/trigger"), 200)
        response = await client.get(f"/api/v1/pipelines/observations/{schedule_id}")
        assert_status_code(response, 200)
        assert response.json()["config"]["repository"] == "owner/app"
        assert response.json()["pulls"][0]["result"]["status"] == "passed"
        assert (await session.execute(select(ScheduleJob))).scalar_one().status == "success"

        # Editing the connection invalidates the stored report instead of serving a stale contract.
        response = await client.put(
            f"/api/v1/projects/{project['id']}",
            json={
                "name": project["name"],
                "repository": project["repository"],
                "github_connector_id": project["github_connector_id"],
                "verification": {**VERIFICATION, "required_jobs": ["lint", "test", "build"]},
                "expected_revision": project["revision"],
            },
        )
        assert_status_code(response, 200)
        assert_status_code(await client.get(f"/api/v1/pipelines/observations/{schedule_id}"), 404)

    async def test_disabled_project_fails_the_run_instead_of_observing(
        self, client, project, project_payload, github_scenario, session
    ):
        response = await client.post(
            "/api/v1/schedule_configs",
            json={
                "name": "observe-app",
                "task_func": "pipeline.observe_project",
                "interval_seconds": 300,
                "payload": {"project_id": project["id"], "pull_numbers": [42]},
            },
        )
        assert_status_code(response, 201)
        schedule_id = response.json()["id"]
        assert_status_code(
            await client.put(
                f"/api/v1/projects/{project['id']}",
                json={**project_payload, "enabled": False, "expected_revision": project["revision"]},
            ),
            200,
        )
        await make_due(session, schedule_id)

        assert_status_code(await client.post("/api/v1/dispatchers/trigger"), 200)
        assert_status_code(await client.get(f"/api/v1/pipelines/observations/{schedule_id}"), 404)
        assert (await session.execute(select(ScheduleJob))).scalar_one().status == "failure"
        assert not github_scenario.requests

    async def test_project_observation_is_published_in_task_specs(self, client, github_scenario):
        from app.features.execution.tasks.usecases.task_spec import GetTaskSpecUseCase

        GetTaskSpecUseCase.clear_cache()
        response = await client.get("/api/v1/tasks/specs?name=pipeline.observe_project")
        assert_status_code(response, 200)
        assert response.json()[0]["payload_schema"]["title"] == "ProjectObservationPayload"


class TestLegacyScheduleImport:
    @pytest.fixture
    async def legacy_schedule(self, client, github_connector) -> dict:
        payload = {
            "repository": "owner/app",
            "github_connector_id": github_connector,
            "pull_numbers": [42, 43],
            "verification": VERIFICATION,
        }
        response = await client.post(
            "/api/v1/schedule_configs",
            json={
                "name": "observe-app",
                "task_func": "pipeline.observe",
                "interval_seconds": 300,
                "payload": payload,
            },
        )
        assert_status_code(response, 201)
        return response.json()

    async def test_import_creates_the_project_and_repoints_the_schedule(self, client, legacy_schedule):
        response = await client.post("/api/v1/projects/import_schedule", json={"schedule_id": legacy_schedule["id"]})
        assert_status_code(response, 200)
        project = response.json()
        assert project["repository"] == "owner/app"
        assert project["verification"]["required_jobs"] == ["lint", "test"]

        schedule = await client.get(f"/api/v1/schedule_configs/{legacy_schedule['id']}")
        assert_status_code(schedule, 200)
        assert schedule.json()["task_func"] == "pipeline.observe_project"
        assert schedule.json()["payload"] == {"project_id": project["id"], "pull_numbers": [42, 43]}
        assert schedule.json()["interval_seconds"] == legacy_schedule["interval_seconds"]
        assert schedule.json()["enabled"] == legacy_schedule["enabled"]

    async def test_import_is_idempotent(self, client, legacy_schedule):
        first = await client.post("/api/v1/projects/import_schedule", json={"schedule_id": legacy_schedule["id"]})
        assert_status_code(first, 200)
        second = await client.post("/api/v1/projects/import_schedule", json={"schedule_id": legacy_schedule["id"]})
        assert_status_code(second, 200)
        assert second.json()["id"] == first.json()["id"]
        assert (await client.get("/api/v1/projects")).json()["total_count"] == 1

    async def test_import_reuses_an_identical_existing_project(self, client, legacy_schedule, project_payload):
        existing = await client.post("/api/v1/projects", json=project_payload)
        assert_status_code(existing, 201)
        response = await client.post("/api/v1/projects/import_schedule", json={"schedule_id": legacy_schedule["id"]})
        assert_status_code(response, 200)
        assert response.json()["id"] == existing.json()["id"]
        assert (await client.get("/api/v1/projects")).json()["total_count"] == 1

    async def test_conflicting_legacy_configuration_migrates_nothing(self, client, legacy_schedule, project_payload):
        payload = {**project_payload, "verification": {**VERIFICATION, "required_jobs": ["lint"]}}
        assert_status_code(await client.post("/api/v1/projects", json=payload), 201)
        response = await client.post("/api/v1/projects/import_schedule", json={"schedule_id": legacy_schedule["id"]})
        assert_status_code(response, 409)
        schedule = await client.get(f"/api/v1/schedule_configs/{legacy_schedule['id']}")
        assert schedule.json()["task_func"] == "pipeline.observe"
        assert schedule.json()["payload"]["pull_numbers"] == [42, 43]

    async def test_unrelated_or_unknown_schedules_are_refused(self, client, github_scenario, session):
        unrelated = ScheduleConfig(
            name="unrelated", task_func="calendar.reconcile_chain", interval_seconds=300, payload={}, enabled=True
        )
        session.add(unrelated)
        await session.commit()

        response = await client.post("/api/v1/projects/import_schedule", json={"schedule_id": str(unrelated.id)})
        assert_status_code(response, 422)
        response = await client.post("/api/v1/projects/import_schedule", json={"schedule_id": str(uuid4())})
        assert_status_code(response, 404)
        assert (await client.get("/api/v1/projects")).json()["total_count"] == 0

    async def test_a_corrupt_legacy_payload_is_refused_instead_of_guessed(self, client, github_scenario, session):
        broken = ScheduleConfig(
            name="observe-app",
            task_func="pipeline.observe",
            interval_seconds=300,
            payload={"repository": "owner/app"},
            enabled=True,
        )
        session.add(broken)
        await session.commit()

        response = await client.post("/api/v1/projects/import_schedule", json={"schedule_id": str(broken.id)})
        assert_status_code(response, 422)
        assert (await client.get("/api/v1/projects")).json()["total_count"] == 0


class TestTemplates:
    async def test_templates_are_versioned_and_installable(self, client, github_scenario):
        response = await client.get("/api/v1/projects/templates")
        assert_status_code(response, 200)
        templates = response.json()
        assert {template["id"] for template in templates} == {"python-uv", "node-npm"}
        for template in templates:
            assert template["filename"] == "ci.yml"
            assert template["version"]
            assert template["changelog"]
            assert "on:" in template["content"]

    async def test_selecting_a_template_records_the_version_it_was_saved_with(self, client, project_payload):
        response = await client.post("/api/v1/projects", json={**project_payload, "template_id": "python-uv"})
        assert_status_code(response, 201)
        templates = (await client.get("/api/v1/projects/templates")).json()
        version = next(template["version"] for template in templates if template["id"] == "python-uv")
        assert response.json()["template_version"] == version


class TestProjectDispatchScheduleLifecycle:
    async def test_project_automatically_creates_syncs_and_deletes_dispatch_schedule(self, client, project_payload):
        # 1. Project creation automatically creates a dispatch schedule
        res = await client.post("/api/v1/projects", json=project_payload)
        assert_status_code(res, 201)
        project = res.json()

        schedules = (await client.get("/api/v1/schedule_configs")).json()["items"]
        dispatch_sched = next(
            (
                s
                for s in schedules
                if s["task_func"] == "pipeline.dispatch_project" and s["payload"].get("project_id") == project["id"]
            ),
            None,
        )
        assert dispatch_sched is not None
        assert dispatch_sched["name"] == f"Dispatch {project['name']}"
        assert dispatch_sched["enabled"] is True
        assert dispatch_sched["interval_seconds"] == 60

        # 2. Updating project name/enabled syncs the dispatch schedule
        update_res = await client.put(
            f"/api/v1/projects/{project['id']}",
            json={**project_payload, "name": "Renamed App", "enabled": False, "expected_revision": project["revision"]},
        )
        assert_status_code(update_res, 200)

        schedules = (await client.get("/api/v1/schedule_configs")).json()["items"]
        dispatch_sched = next(
            (
                s
                for s in schedules
                if s["task_func"] == "pipeline.dispatch_project" and s["payload"].get("project_id") == project["id"]
            ),
            None,
        )
        assert dispatch_sched is not None
        assert dispatch_sched["name"] == "Dispatch Renamed App"
        assert dispatch_sched["enabled"] is False

        # 3. Deleting project automatically cleans up the dispatch schedule
        del_res = await client.delete(f"/api/v1/projects/{project['id']}")
        assert_status_code(del_res, 204)

        schedules = (await client.get("/api/v1/schedule_configs")).json()["items"]
        dispatch_sched = next(
            (
                s
                for s in schedules
                if s["task_func"] == "pipeline.dispatch_project" and s["payload"].get("project_id") == project["id"]
            ),
            None,
        )
        assert dispatch_sched is None
