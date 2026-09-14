from datetime import UTC, datetime, timedelta
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.features.project_management.pipeline_runs.models import (
    ExecutionAttempt,
    ExecutionAttemptState,
    ExecutionDelivery,
    PipelineRun,
    PipelineRunState,
)
from app.features.project_management.pipeline_runs.schemas import (
    AttachPRRequest,
    CompleteAttemptRequest,
    LeaseGrant,
    PauseRunRequest,
)
from app.features.project_management.pipeline_runs.usecases.lifecycle import PipelineRunUseCase

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
    run.execution_provider_id = uuid4()
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
    run.epoch = 1
    run.lease_owner = "worker-1"
    run.lease_token = uuid4()
    run.lease_expires_at = datetime.now(UTC)
    run.next_action_at = None
    run.quota_block_count = 0
    run.created_at = datetime.now(UTC)
    run.updated_at = datetime.now(UTC)
    return run


@pytest.mark.parametrize("delivery_number", [1, 3])
async def test_quota_reply_sets_a_global_provider_hold_without_a_run_retry_cap(delivery_number):
    repo = MagicMock()
    projects = MagicMock()
    observer = MagicMock()
    providers = MagicMock()
    providers.record_quota_event = AsyncMock()
    use_case = PipelineRunUseCase(repo, projects, observer, providers)
    run = create_mock_run()
    project = MagicMock(enabled=True, revision=1, github_repository="owner/repo", github_connector_id=uuid4())
    attempt = MagicMock(spec=ExecutionAttempt)
    attempt.id = uuid4()
    attempt.request_snapshot = {"pull_request": run.pull_snapshot}
    delivery = MagicMock(spec=ExecutionDelivery)
    delivery.delivery_number = delivery_number
    delivery.posted_at = datetime.now(UTC)

    repo.get_leased = AsyncMock(return_value=run)
    repo.active_attempt = AsyncMock(return_value=attempt)
    repo.latest_delivery = AsyncMock(return_value=delivery)
    repo.create_delivery = AsyncMock()
    projects.get = AsyncMock(return_value=project)
    observer.get_pull_request = AsyncMock(return_value={"state": "open", "head": {"sha": "a" * 40}})
    observer.list_pull_comments = AsyncMock(
        return_value=[
            {
                "user": {"login": "chatgpt-codex-connector"},
                "body": "You reached a Codex usage limit.",
                "created_at": delivery.posted_at.isoformat(),
            }
        ]
    )

    mock_tx = MagicMock()
    mock_session = AsyncMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.features.project_management.pipeline_runs.usecases.lifecycle.AsyncTransaction", lambda: mock_tx)
        result = await use_case.advance_run(run.id, owner="worker-1", token=run.lease_token, observer=observer)

    assert result.state == PipelineRunState.DISPATCHING
    assert run.next_action_at is None
    assert run.pause_reason is None
    providers.record_quota_event.assert_awaited_once()


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


async def test_manual_advance_prepares_and_dispatches_a_queued_run():
    repo = MagicMock()
    projects = MagicMock()
    observer = MagicMock()
    use_case = PipelineRunUseCase(repo, projects, observer)
    queued_run = create_mock_run(state=PipelineRunState.QUEUED)
    dispatching_run = create_mock_run(state=PipelineRunState.DISPATCHING)
    grant = LeaseGrant(
        run_id=queued_run.id,
        owner="manual:test",
        token=uuid4(),
        expires_at=datetime.now(UTC),
        run_revision=queued_run.revision,
    )
    expected = MagicMock()

    use_case.acquire_lease = AsyncMock(return_value=grant)
    use_case.get = AsyncMock(side_effect=[queued_run, dispatching_run])
    use_case.prepare_implementation = AsyncMock()
    use_case.dispatch_implementation = AsyncMock(return_value=expected)
    use_case.release_lease = AsyncMock()

    result = await use_case.manual_advance(queued_run.id, observer)

    assert result is expected
    assert use_case.prepare_implementation.await_count == 1
    assert use_case.prepare_implementation.await_args is not None
    prep_run_id, prep_req = use_case.prepare_implementation.await_args.args
    assert prep_run_id == queued_run.id
    assert prep_req.token == grant.token
    assert prep_req.expected_run_revision == grant.run_revision
    use_case.dispatch_implementation.assert_awaited_once_with(queued_run.id, owner=ANY, token=grant.token)
    use_case.release_lease.assert_awaited_once()


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
            mp.setattr(
                "app.features.project_management.pipeline_runs.usecases.lifecycle.AsyncTransaction", lambda: mock_tx
            )
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
    mock_run.branch = "feature"
    repo.get = AsyncMock(return_value=mock_run)
    repo.active_attempt = AsyncMock(return_value=None)
    repo.list_attempts = AsyncMock(return_value=[])
    repo.next_attempt_number = AsyncMock(return_value=1)
    repo.create_attempt = AsyncMock(return_value=MagicMock(id=uuid4()))
    repo.create_delivery = AsyncMock()
    projects.get = AsyncMock(
        return_value=MagicMock(enabled=True, revision=1, github_repository="owner/repo", github_connector_id=uuid4())
    )
    selector.get_pull_request = AsyncMock(
        return_value={"state": "open", "head": {"sha": "b" * 40, "ref": "feature"}, "base": {"ref": "main"}}
    )

    with MagicMock() as mock_tx:
        mock_session = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_tx.__aexit__ = AsyncMock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.features.project_management.pipeline_runs.usecases.lifecycle.AsyncTransaction", lambda: mock_tx
            )
            res = await use_case.resume_run(mock_run.id)

            assert mock_run.state == PipelineRunState.DISPATCHING
            assert mock_run.pause_reason is None
            assert res.state == PipelineRunState.DISPATCHING


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
            mp.setattr(
                "app.features.project_management.pipeline_runs.usecases.lifecycle.AsyncTransaction", lambda: mock_tx
            )
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
            mp.setattr(
                "app.features.project_management.pipeline_runs.usecases.lifecycle.AsyncTransaction", lambda: mock_tx
            )
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
    mock_attempt.epoch = 1
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
            mp.setattr(
                "app.features.project_management.pipeline_runs.usecases.lifecycle.AsyncTransaction", lambda: mock_tx
            )
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


async def test_dispatch_waits_until_next_action_without_reading_github(monkeypatch):
    run = create_mock_run(state=PipelineRunState.DISPATCHING)
    run.next_action_at = datetime.now(UTC) + timedelta(hours=5)
    repo = MagicMock()
    repo.get_leased = AsyncMock(return_value=run)
    projects = MagicMock()
    projects.get = AsyncMock(side_effect=AssertionError("Waiting dispatch must not resolve its project"))
    observer = MagicMock()
    observer.get_token = AsyncMock(side_effect=AssertionError("Waiting dispatch must not call GitHub"))
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=AsyncMock())
    tx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.features.project_management.pipeline_runs.usecases.lifecycle.AsyncTransaction", lambda: tx)

    result = await PipelineRunUseCase(repo, projects, observer).dispatch_implementation(
        run.id, owner="worker-1", token=run.lease_token
    )

    assert result.state == PipelineRunState.DISPATCHING
    assert result.next_action_at == run.next_action_at
    projects.get.assert_not_awaited()
    observer.get_token.assert_not_awaited()


@pytest.mark.parametrize("elapsed_hours", [1, 3, 12])
async def test_pushed_head_wins_over_watchdog_and_quota_replies(monkeypatch, elapsed_hours):
    run = create_mock_run()
    repo = MagicMock()
    repo.get_leased = AsyncMock(return_value=run)
    attempt = MagicMock(spec=ExecutionAttempt)
    attempt.id = uuid4()
    attempt.request_snapshot = {"pull_request": run.pull_snapshot}
    repo.active_attempt = AsyncMock(return_value=attempt)
    delivery = MagicMock(spec=ExecutionDelivery)
    delivery.posted_at = datetime.now(UTC) - timedelta(hours=elapsed_hours)
    repo.latest_delivery = AsyncMock(return_value=delivery)
    repo.create_delivery = AsyncMock()
    projects = MagicMock()
    projects.get = AsyncMock(
        return_value=MagicMock(enabled=True, revision=1, github_repository="owner/repo", github_connector_id=uuid4())
    )
    observer = MagicMock()
    observer.get_pull_request = AsyncMock(return_value={"state": "open", "head": {"sha": "b" * 40}})
    observer.list_pull_comments = AsyncMock(
        return_value=[{"user": {"login": "chatgpt-codex-connector"}, "body": "Codex usage limit"}]
    )
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=AsyncMock())
    tx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.features.project_management.pipeline_runs.usecases.lifecycle.AsyncTransaction", lambda: tx)

    result = await PipelineRunUseCase(repo, projects, observer).advance_run(
        run.id, owner="worker-1", token=run.lease_token, observer=observer
    )

    assert result.state == PipelineRunState.AWAITING_CI
    repo.create_delivery.assert_not_awaited()
    observer.list_pull_comments.assert_not_awaited()
    observer.get_pull_request.assert_awaited_once_with(
        projects.get.return_value.github_connector_id, "owner/repo", run.pull_number
    )


@pytest.mark.parametrize(
    ("elapsed", "expected_state"),
    [
        (timedelta(hours=2, minutes=4, seconds=59), PipelineRunState.IMPLEMENTING),
        (timedelta(hours=2, minutes=5), PipelineRunState.DISPATCHING),
        (timedelta(hours=2, minutes=5, seconds=1), PipelineRunState.DISPATCHING),
    ],
)
async def test_silent_watchdog_uses_an_exact_fixed_clock(monkeypatch, elapsed, expected_state):
    """The silent-retry boundary must not depend on wall-clock test timing."""
    from app.features.project_management.pipeline_runs.usecases import lifecycle

    frozen_now = datetime(2026, 9, 14, 12, tzinfo=UTC)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen_now if tz else frozen_now.replace(tzinfo=None)

    run = create_mock_run()
    repo, projects, observer = MagicMock(), MagicMock(), MagicMock()
    attempt = MagicMock(spec=ExecutionAttempt)
    attempt.id = uuid4()
    attempt.request_snapshot = {"pull_request": run.pull_snapshot}
    delivery = MagicMock(spec=ExecutionDelivery)
    delivery.delivery_number = 1
    delivery.posted_at = frozen_now - elapsed
    project = MagicMock(enabled=True, revision=1, github_repository="owner/repo", github_connector_id=uuid4())
    repo.get_leased = AsyncMock(return_value=run)
    repo.active_attempt = AsyncMock(return_value=attempt)
    repo.latest_delivery = AsyncMock(return_value=delivery)
    repo.list_deliveries = AsyncMock(return_value=[])
    repo.create_delivery = AsyncMock()
    projects.get = AsyncMock(return_value=project)
    observer.get_pull_request = AsyncMock(return_value={"state": "open", "head": {"sha": "a" * 40}})
    observer.list_pull_comments = AsyncMock(return_value=[])
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=AsyncMock())
    tx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(lifecycle, "datetime", FrozenDateTime)
    monkeypatch.setattr(lifecycle, "AsyncTransaction", lambda: tx)

    result = await PipelineRunUseCase(repo, projects, observer).advance_run(
        run.id, owner="worker-1", token=run.lease_token, observer=observer
    )

    assert result.state == expected_state
    if expected_state == PipelineRunState.IMPLEMENTING:
        repo.create_delivery.assert_not_awaited()
    else:
        repo.create_delivery.assert_awaited_once()
