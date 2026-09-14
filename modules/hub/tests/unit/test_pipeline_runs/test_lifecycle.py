from datetime import UTC, datetime
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.features.pipeline_runs.models import ExecutionAttempt, ExecutionAttemptState, PipelineRun, PipelineRunState
from app.features.pipeline_runs.schemas import (
    AttachPRRequest,
    CompleteAttemptRequest,
    LeaseGrant,
    PauseRunRequest,
)
from app.features.pipeline_runs.usecases import PipelineRunUseCase

pytestmark = pytest.mark.unit


def create_mock_run(
    run_id=None,
    state=PipelineRunState.IMPLEMENTING,
    pull_number=10,
    pull_url=None,
):
    run = MagicMock(spec=PipelineRun)
    run.id = run_id or uuid4()
    run.project_id = uuid4()
    run.project_revision = 1
    run.pull_number = pull_number
    run.pull_url = pull_url or f"https://github.com/test-org/test-repo/pull/{pull_number}"
    run.pull_snapshot = {
        "number": pull_number,
        "url": run.pull_url,
        "title": "Test PR",
        "body": "Test description",
        "base_ref": "main",
        "head_ref": "feature",
        "head_sha": "a" * 40,
        "linked_issues": [],
    }
    run.state = state
    run.pause_reason = None
    run.branch = "codex/pr-10"
    run.revision = 1
    run.lease_owner = "worker-1"
    run.lease_token = uuid4()
    run.lease_expires_at = datetime.now(UTC)
    run.created_at = datetime.now(UTC)
    run.updated_at = datetime.now(UTC)
    return run


async def test_manual_advance_dispatches_a_prepared_implementation():
    repo = MagicMock()
    projects = MagicMock()
    observer = MagicMock()
    use_case = PipelineRunUseCase(repo, projects, observer)
    run = create_mock_run(state=PipelineRunState.DISPATCHING)
    grant = LeaseGrant(
        run_id=run.id,
        owner="manual:test",
        token=uuid4(),
        expires_at=datetime.now(UTC),
        run_revision=run.revision,
    )
    expected = MagicMock()

    use_case.acquire_lease = AsyncMock(return_value=grant)
    use_case.get = AsyncMock(return_value=run)
    use_case.dispatch_implementation = AsyncMock(return_value=expected)
    use_case.release_lease = AsyncMock()

    result = await use_case.manual_advance(run.id, observer)

    assert result is expected
    use_case.dispatch_implementation.assert_awaited_once_with(run.id, owner=ANY, token=grant.token)
    assert use_case.release_lease.await_args is not None
    assert use_case.dispatch_implementation.await_args is not None
    release_request = use_case.release_lease.await_args.args[1]
    assert release_request.token == grant.token
    assert release_request.owner == use_case.dispatch_implementation.await_args.kwargs["owner"]


async def test_pause_run_transitions_state_and_clears_lease():
    repo = MagicMock()
    projects = MagicMock()
    selector = MagicMock()
    use_case = PipelineRunUseCase(repo, projects, selector)

    mock_run = create_mock_run()
    repo.get = AsyncMock(return_value=mock_run)

    with MagicMock() as mock_tx:
        mock_session = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_tx.__aexit__ = AsyncMock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.features.pipeline_runs.usecases.AsyncTransaction", lambda: mock_tx)
            res = await use_case.pause_run(mock_run.id, PauseRunRequest(reason="Maintenance"))

            assert mock_run.state == PipelineRunState.PAUSED
            assert mock_run.pause_reason == "Maintenance"
            assert mock_run.lease_owner is None
            assert mock_run.revision == 2
            assert res.state == PipelineRunState.PAUSED


async def test_resume_run_transitions_paused_run_back_to_active():
    repo = MagicMock()
    projects = MagicMock()
    selector = MagicMock()
    use_case = PipelineRunUseCase(repo, projects, selector)

    mock_run = create_mock_run(state=PipelineRunState.PAUSED, pull_number=42)
    repo.get = AsyncMock(return_value=mock_run)

    with MagicMock() as mock_tx:
        mock_session = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_tx.__aexit__ = AsyncMock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.features.pipeline_runs.usecases.AsyncTransaction", lambda: mock_tx)
            res = await use_case.resume_run(mock_run.id)

            assert mock_run.state == PipelineRunState.AWAITING_CI
            assert mock_run.pause_reason is None
            assert res.state == PipelineRunState.AWAITING_CI


async def test_cancel_run_marks_run_and_active_attempt_canceled():
    repo = MagicMock()
    projects = MagicMock()
    selector = MagicMock()
    use_case = PipelineRunUseCase(repo, projects, selector)

    mock_run = create_mock_run()
    repo.get = AsyncMock(return_value=mock_run)

    mock_attempt = MagicMock(spec=ExecutionAttempt)
    mock_attempt.state = ExecutionAttemptState.RUNNING
    mock_attempt.finished_at = None
    repo.active_attempt = AsyncMock(return_value=mock_attempt)

    with MagicMock() as mock_tx:
        mock_session = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_tx.__aexit__ = AsyncMock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.features.pipeline_runs.usecases.AsyncTransaction", lambda: mock_tx)
            res = await use_case.cancel_run(mock_run.id)

            assert mock_run.state == PipelineRunState.CANCELED
            assert mock_attempt.state == ExecutionAttemptState.FAILED
            assert mock_attempt.failure_code == "CANCELED"
            assert mock_attempt.finished_at is not None
            assert res.state == PipelineRunState.CANCELED


async def test_attach_pr_transitions_to_awaiting_ci():
    repo = MagicMock()
    projects = MagicMock()
    selector = MagicMock()
    use_case = PipelineRunUseCase(repo, projects, selector)

    mock_run = create_mock_run(state=PipelineRunState.DISPATCHING)
    repo.get = AsyncMock(return_value=mock_run)

    mock_project = MagicMock()
    mock_project.github_repository = "org/auto-hub"
    projects.get = AsyncMock(return_value=mock_project)

    mock_attempt = MagicMock(spec=ExecutionAttempt)
    mock_attempt.state = ExecutionAttemptState.PLANNED
    repo.active_attempt = AsyncMock(return_value=mock_attempt)

    with MagicMock() as mock_tx:
        mock_session = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_tx.__aexit__ = AsyncMock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.features.pipeline_runs.usecases.AsyncTransaction", lambda: mock_tx)
            req = AttachPRRequest(pull_number=99)
            res = await use_case.attach_pr(mock_run.id, req)

            assert mock_run.pull_number == 99
            assert "99" in mock_run.pull_url
            assert mock_run.state == PipelineRunState.AWAITING_CI
            assert mock_attempt.state == ExecutionAttemptState.RUNNING
            assert res.pull_number == 99


async def test_complete_attempt_records_result():
    repo = MagicMock()
    projects = MagicMock()
    selector = MagicMock()
    use_case = PipelineRunUseCase(repo, projects, selector)

    mock_run = create_mock_run()
    repo.get = AsyncMock(return_value=mock_run)

    attempt_id = uuid4()
    mock_attempt = MagicMock(spec=ExecutionAttempt)
    mock_attempt.id = attempt_id
    mock_attempt.pipeline_run_id = mock_run.id
    mock_attempt.attempt_number = 1
    mock_attempt.kind = "implementation"
    mock_attempt.state = ExecutionAttemptState.RUNNING
    mock_attempt.request_snapshot = {}
    mock_attempt.request_digest = "digest"
    mock_attempt.idempotency_key = uuid4()
    mock_attempt.external_correlation_id = None
    mock_attempt.external_status = None
    mock_attempt.conversation_url = None
    mock_attempt.started_at = datetime.now(UTC)
    mock_attempt.finished_at = None
    mock_attempt.failure_code = None
    mock_attempt.failure_detail = None
    mock_attempt.created_at = datetime.now(UTC)
    mock_attempt.updated_at = datetime.now(UTC)

    repo.get_attempt = AsyncMock(return_value=mock_attempt)

    with MagicMock() as mock_tx:
        mock_session = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_tx.__aexit__ = AsyncMock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.features.pipeline_runs.usecases.AsyncTransaction", lambda: mock_tx)
            req = CompleteAttemptRequest(
                status="failed",
                failure_code="BUILD_ERR",
                failure_detail="Compilation failed",
            )
            res = await use_case.complete_attempt(mock_run.id, attempt_id, req)

            assert mock_attempt.state == ExecutionAttemptState.FAILED
            assert mock_attempt.failure_code == "BUILD_ERR"
            assert mock_run.state == PipelineRunState.FAILED
            assert res.state == ExecutionAttemptState.FAILED


async def test_manual_advance_leases_and_advances():
    repo = MagicMock()
    projects = MagicMock()
    selector = MagicMock()
    use_case = PipelineRunUseCase(repo, projects, selector)

    run_id = uuid4()
    observer = MagicMock()

    grant = MagicMock(spec=LeaseGrant)
    grant.token = uuid4()
    use_case.acquire_lease = AsyncMock(return_value=grant)
    use_case.get = AsyncMock(return_value=MagicMock(state=PipelineRunState.AWAITING_CI))
    use_case.advance_run = AsyncMock(return_value=MagicMock())
    use_case.release_lease = AsyncMock()

    await use_case.manual_advance(run_id, observer)

    use_case.acquire_lease.assert_awaited_once()
    use_case.advance_run.assert_awaited_once()
    use_case.release_lease.assert_awaited_once()
