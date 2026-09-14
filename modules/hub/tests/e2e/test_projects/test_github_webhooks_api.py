import hashlib
import hmac

import pytest
from app.common.config import get_github_webhook_config
from app.features.project_management.github_webhooks.models import GitHubWebhookDelivery  # noqa: F401

pytestmark = pytest.mark.e2e


def _headers(body: bytes, delivery: str = "delivery-1") -> dict[str, str]:
    secret = b"webhook-test-secret"
    return {
        "X-GitHub-Delivery": delivery,
        "X-GitHub-Event": "ping",
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
