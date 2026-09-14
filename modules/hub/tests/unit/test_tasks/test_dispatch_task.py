from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.features.execution.tasks.core.context import task_context
from app.features.execution.tasks.domains.pipeline.task import dispatch_project_task
from app.features.project_management.pipeline_runs.models import PipelineRun, PipelineRunState
from app.features.project_management.pipeline_runs.schemas import LeaseGrant
from app.features.project_management.projects.schemas import ProjectDispatchPayload

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def mock_credential_provider(monkeypatch, credential_key_provider):
    monkeypatch.setattr(
        "app.features.execution.tasks.domains.pipeline.task.get_credential_key_provider",
        lambda: credential_key_provider,
    )


async def test_dispatch_task_fails_outside_task_context():
    payload = ProjectDispatchPayload(project_id=uuid4())
    with pytest.raises(RuntimeError, match="requires a schedule task context"):
        await dispatch_project_task(payload)


async def test_dispatch_task_noops_when_no_active_run():
    project_id = uuid4()
    with (
        task_context(config_id=uuid4(), config_name="test", run_id=uuid4()),
        patch("app.features.execution.tasks.domains.pipeline.task.PipelineRunRepository") as mock_repo_cls,
    ):
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_active = AsyncMock(return_value=None)

        await dispatch_project_task(ProjectDispatchPayload(project_id=project_id))

        mock_repo.get_active.assert_awaited_once()


async def test_dispatch_task_acquires_lease_and_prepares_implementation_for_queued_run():
    project_id = uuid4()
    run_id = uuid4()
    lease_token = uuid4()

    mock_run = MagicMock(spec=PipelineRun)
    mock_run.id = run_id
    mock_run.state = PipelineRunState.QUEUED
    mock_run.next_action_at = None

    grant = MagicMock(spec=LeaseGrant)
    grant.token = lease_token
    grant.run_revision = 1

    with (
        task_context(config_id=uuid4(), config_name="test", run_id=uuid4()),
        patch("app.features.execution.tasks.domains.pipeline.task.PipelineRunRepository") as mock_repo_cls,
        patch("app.features.execution.tasks.domains.pipeline.task.PipelineRunUseCase") as mock_use_case_cls,
    ):
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_active = AsyncMock(return_value=mock_run)

        mock_use_case = mock_use_case_cls.return_value
        mock_use_case.acquire_lease = AsyncMock(return_value=grant)
        mock_use_case.prepare_implementation = AsyncMock()
        mock_use_case.release_lease = AsyncMock()

        await dispatch_project_task(ProjectDispatchPayload(project_id=project_id))

        mock_repo.get_active.assert_awaited_once()
        mock_use_case.acquire_lease.assert_awaited_once()
        mock_use_case.prepare_implementation.assert_awaited_once()
        mock_use_case.release_lease.assert_awaited_once()


async def test_dispatch_task_acquires_lease_and_delivers_a_prepared_implementation():
    project_id = uuid4()
    run_id = uuid4()
    lease_token = uuid4()

    mock_run = MagicMock(spec=PipelineRun)
    mock_run.id = run_id
    mock_run.state = PipelineRunState.DISPATCHING
    mock_run.next_action_at = None

    grant = MagicMock(spec=LeaseGrant)
    grant.token = lease_token
    grant.run_revision = 2

    with (
        task_context(config_id=uuid4(), config_name="test", run_id=uuid4()),
        patch("app.features.execution.tasks.domains.pipeline.task.PipelineRunRepository") as mock_repo_cls,
        patch("app.features.execution.tasks.domains.pipeline.task.PipelineRunUseCase") as mock_use_case_cls,
    ):
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_active = AsyncMock(return_value=mock_run)

        mock_use_case = mock_use_case_cls.return_value
        mock_use_case.acquire_lease = AsyncMock(return_value=grant)
        mock_use_case.dispatch_implementation = AsyncMock(return_value=mock_run)
        mock_use_case.release_lease = AsyncMock()

        await dispatch_project_task(ProjectDispatchPayload(project_id=project_id))

        mock_repo.get_active.assert_awaited_once()
        mock_use_case.acquire_lease.assert_awaited_once()
        mock_use_case.dispatch_implementation.assert_awaited_once_with(run_id, owner=ANY, token=lease_token)
        mock_use_case.release_lease.assert_awaited_once()
