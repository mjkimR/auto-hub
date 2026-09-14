import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.common.config import get_github_webhook_config
from app.features.project_management.github_webhooks.models import GitHubWebhookDelivery  # noqa: F401
from app.features.project_management.github_webhooks.usecases import (
    AUTO_RUN_TRIGGER,
    GitHubWebhookUseCase,
    _extract_trigger_text,
)
from app.features.project_management.pipeline_runs.schemas import EnrollPullRequest

pytestmark = pytest.mark.e2e


def _headers(body: bytes, delivery: str = "delivery-1", event: str = "ping") -> dict[str, str]:
    secret = b"webhook-test-secret"
    return {
        "X-GitHub-Delivery": delivery,
        "X-GitHub-Event": event,
        "X-Hub-Signature-256": "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest(),
        "Content-Type": "application/json",
    }


async def test_github_webhook_verifies_signature_and_deduplicates(client, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "webhook-test-secret")
    get_github_webhook_config.cache_clear()
    body = b'{"repository":{"full_name":"owner/repository"}}'

    payload = {"repository": {"full_name": "owner/repository"}}
    response = await client.post("/api/github/webhooks", json=payload, headers=_headers(body))
    duplicate = await client.post("/api/github/webhooks", json=payload, headers=_headers(body))

    assert response.request.content == body
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert duplicate.status_code == 202
    assert duplicate.json() == {"status": "duplicate"}
    get_github_webhook_config.cache_clear()


async def test_github_webhook_rejects_invalid_signature(client, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "webhook-test-secret")
    get_github_webhook_config.cache_clear()
    body = b"{}"
    headers = _headers(body)
    headers["X-Hub-Signature-256"] = "sha256=not-valid"

    response = await client.post("/api/github/webhooks", json={}, headers=headers)

    assert response.status_code == 401
    get_github_webhook_config.cache_clear()


def test_auto_run_regex_matching():
    assert AUTO_RUN_TRIGGER.search("@auto-run")
    assert AUTO_RUN_TRIGGER.search("@Auto-Run please do this")
    assert AUTO_RUN_TRIGGER.search("Please review this PR @AUTO-RUN\nThanks!")
    assert not AUTO_RUN_TRIGGER.search("@auto-running")
    assert not AUTO_RUN_TRIGGER.search("no trigger here")


def test_extract_trigger_text():
    # PR opened with body
    assert (
        _extract_trigger_text("pull_request", {"action": "opened", "pull_request": {"body": "hello @auto-run"}})
        == "hello @auto-run"
    )
    # PR reopened with body
    assert (
        _extract_trigger_text("pull_request", {"action": "reopened", "pull_request": {"body": "recheck @auto-run"}})
        == "recheck @auto-run"
    )
    # PR closed (ignored)
    assert _extract_trigger_text("pull_request", {"action": "closed", "pull_request": {"body": "done"}}) is None

    # Issue comment on PR
    pr_comment = {
        "action": "created",
        "issue": {"number": 12, "pull_request": {"url": "https://api.github.com/repos/owner/repo/pulls/12"}},
        "comment": {"body": "@auto-run run tests"},
    }
    assert _extract_trigger_text("issue_comment", pr_comment) == "@auto-run run tests"

    # Issue comment on regular issue (not PR)
    issue_comment = {
        "action": "created",
        "issue": {"number": 12},
        "comment": {"body": "@auto-run run tests"},
    }
    assert _extract_trigger_text("issue_comment", issue_comment) is None

    # Deleted comment
    deleted_comment = {
        "action": "deleted",
        "issue": {"number": 12, "pull_request": {}},
        "comment": {"body": "@auto-run"},
    }
    assert _extract_trigger_text("issue_comment", deleted_comment) is None


async def test_webhook_pr_opened_with_auto_run_enrolls_and_advances():
    repo = MagicMock()
    runs = MagicMock()
    lifecycle = MagicMock()
    lifecycle.observer = MagicMock()

    project = MagicMock(id=uuid4(), enabled=True)
    repo.project_for_repository = AsyncMock(return_value=project)
    runs.get_active_for_pull = AsyncMock(return_value=None)

    new_run = MagicMock(id=uuid4())
    lifecycle.enroll = AsyncMock(return_value=new_run)
    lifecycle.manual_advance = AsyncMock()

    webhook = GitHubWebhookUseCase(repo, runs, lifecycle)
    webhook._finish = AsyncMock()

    payload = {
        "action": "opened",
        "repository": {"full_name": "owner/app"},
        "pull_request": {"number": 42, "body": "Feature description\n\n@auto-run please implement"},
    }
    await webhook.process("del-1", payload, event="pull_request")

    lifecycle.enroll.assert_awaited_once_with(project.id, EnrollPullRequest(pull_number=42))
    lifecycle.manual_advance.assert_awaited_once_with(new_run.id, lifecycle.observer)
    webhook._finish.assert_awaited_once_with("del-1", "processed")


async def test_webhook_pr_opened_without_auto_run_is_ignored():
    repo = MagicMock()
    runs = MagicMock()
    lifecycle = MagicMock()

    project = MagicMock(id=uuid4(), enabled=True)
    repo.project_for_repository = AsyncMock(return_value=project)
    runs.get_active_for_pull = AsyncMock(return_value=None)
    lifecycle.enroll = AsyncMock()
    lifecycle.manual_advance = AsyncMock()

    webhook = GitHubWebhookUseCase(repo, runs, lifecycle)
    webhook._finish = AsyncMock()

    payload = {
        "action": "opened",
        "repository": {"full_name": "owner/app"},
        "pull_request": {"number": 42, "body": "Normal human PR without bot mention"},
    }
    await webhook.process("del-2", payload, event="pull_request")

    lifecycle.enroll.assert_not_awaited()
    lifecycle.manual_advance.assert_not_awaited()
    webhook._finish.assert_awaited_once_with("del-2", "processed")


async def test_webhook_comment_with_auto_run_enrolls_when_no_active_run():
    repo = MagicMock()
    runs = MagicMock()
    lifecycle = MagicMock()
    lifecycle.observer = MagicMock()

    project = MagicMock(id=uuid4(), enabled=True)
    repo.project_for_repository = AsyncMock(return_value=project)
    runs.get_active_for_pull = AsyncMock(return_value=None)

    new_run = MagicMock(id=uuid4())
    lifecycle.enroll = AsyncMock(return_value=new_run)
    lifecycle.manual_advance = AsyncMock()

    webhook = GitHubWebhookUseCase(repo, runs, lifecycle)
    webhook._finish = AsyncMock()

    payload = {
        "action": "created",
        "repository": {"full_name": "owner/app"},
        "issue": {"number": 15, "pull_request": {"html_url": "https://..."}},
        "comment": {"body": "@auto-run start this task"},
    }
    await webhook.process("del-3", payload, event="issue_comment")

    lifecycle.enroll.assert_awaited_once_with(project.id, EnrollPullRequest(pull_number=15))
    lifecycle.manual_advance.assert_awaited_once_with(new_run.id, lifecycle.observer)
    webhook._finish.assert_awaited_once_with("del-3", "processed")


async def test_webhook_comment_with_auto_run_advances_existing_active_run():
    repo = MagicMock()
    runs = MagicMock()
    lifecycle = MagicMock()
    lifecycle.observer = MagicMock()

    project = MagicMock(id=uuid4(), enabled=True)
    existing_run = MagicMock(id=uuid4())
    repo.project_for_repository = AsyncMock(return_value=project)
    runs.get_active_for_pull = AsyncMock(return_value=existing_run)

    lifecycle.enroll = AsyncMock()
    lifecycle.manual_advance = AsyncMock()

    webhook = GitHubWebhookUseCase(repo, runs, lifecycle)
    webhook._finish = AsyncMock()

    payload = {
        "action": "created",
        "repository": {"full_name": "owner/app"},
        "issue": {"number": 15, "pull_request": {"html_url": "https://..."}},
        "comment": {"body": "@auto-run retry"},
    }
    await webhook.process("del-4", payload, event="issue_comment")

    lifecycle.enroll.assert_not_awaited()
    lifecycle.manual_advance.assert_awaited_once_with(existing_run.id, lifecycle.observer)
    webhook._finish.assert_awaited_once_with("del-4", "processed")
