from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.features.pipeline_runs.models import PipelineRunState
from app.features.pipeline_runs.schemas import LeaseGrant, PipelineRunAcquisition, PipelineRunRead
from app.features.projects.schemas import ProjectDispatchPayload
from app.features.tasks.core.context import task_context
from app.features.tasks.domains.pipeline.task import dispatch_project_task

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def mock_credential_provider(monkeypatch, credential_key_provider):
    monkeypatch.setattr(
        "app.features.tasks.domains.pipeline.task.get_credential_key_provider", lambda: credential_key_provider
    )


async def test_dispatch_task_fails_outside_task_context():
    payload = ProjectDispatchPayload(project_id=uuid4())
    with pytest.raises(RuntimeError, match="requires a schedule task context"):
        await dispatch_project_task(payload)


async def test_dispatch_task_noops_when_no_run_is_acquired():
    project_id = uuid4()
    with (
        task_context(config_id=uuid4(), config_name="test", run_id=uuid4()),
        patch("app.features.tasks.domains.pipeline.task.PipelineRunUseCase") as mock_use_case_cls,
    ):
        mock_use_case = mock_use_case_cls.return_value
        mock_use_case.acquire = AsyncMock(return_value=PipelineRunAcquisition(run=None, created=False))

        await dispatch_project_task(ProjectDispatchPayload(project_id=project_id))

        mock_use_case.acquire.assert_awaited_once_with(project_id)
        mock_use_case.acquire_lease.assert_not_called()


async def test_dispatch_task_acquires_lease_and_prepares_implementation_for_queued_run():
    project_id = uuid4()
    run_id = uuid4()
    lease_token = uuid4()

    mock_run = MagicMock(spec=PipelineRunRead)
    mock_run.id = run_id
    mock_run.state = PipelineRunState.QUEUED

    grant = MagicMock(spec=LeaseGrant)
    grant.token = lease_token
    grant.run_revision = 1

    with (
        task_context(config_id=uuid4(), config_name="test", run_id=uuid4()),
        patch("app.features.tasks.domains.pipeline.task.PipelineRunUseCase") as mock_use_case_cls,
    ):
        mock_use_case = mock_use_case_cls.return_value
        mock_use_case.acquire = AsyncMock(return_value=PipelineRunAcquisition(run=mock_run, created=True))
        mock_use_case.acquire_lease = AsyncMock(return_value=grant)
        mock_use_case.prepare_implementation = AsyncMock()
        mock_use_case.release_lease = AsyncMock()

        await dispatch_project_task(ProjectDispatchPayload(project_id=project_id))

        mock_use_case.acquire.assert_awaited_once_with(project_id)
        mock_use_case.acquire_lease.assert_awaited_once()
        mock_use_case.prepare_implementation.assert_awaited_once()
        mock_use_case.release_lease.assert_awaited_once()


async def test_dispatch_task_acquires_lease_and_advances_active_run():
    project_id = uuid4()
    run_id = uuid4()
    lease_token = uuid4()

    mock_run = MagicMock(spec=PipelineRunRead)
    mock_run.id = run_id
    mock_run.state = PipelineRunState.DISPATCHING

    grant = MagicMock(spec=LeaseGrant)
    grant.token = lease_token
    grant.run_revision = 2

    with (
        task_context(config_id=uuid4(), config_name="test", run_id=uuid4()),
        patch("app.features.tasks.domains.pipeline.task.PipelineRunUseCase") as mock_use_case_cls,
    ):
        mock_use_case = mock_use_case_cls.return_value
        mock_use_case.acquire = AsyncMock(return_value=PipelineRunAcquisition(run=mock_run, created=False))
        mock_use_case.acquire_lease = AsyncMock(return_value=grant)
        mock_use_case.advance_run = AsyncMock(return_value=mock_run)
        mock_use_case.release_lease = AsyncMock()

        await dispatch_project_task(ProjectDispatchPayload(project_id=project_id))

        mock_use_case.acquire.assert_awaited_once_with(project_id)
        mock_use_case.acquire_lease.assert_awaited_once()
        mock_use_case.advance_run.assert_awaited_once()
        mock_use_case.release_lease.assert_awaited_once()
