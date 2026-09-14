import hashlib
import hmac
from datetime import UTC, datetime
from typing import Any

from app.features.project_management.github_webhooks.models import GitHubWebhookDelivery
from app.features.project_management.github_webhooks.repos import GitHubWebhookRepository
from app.features.project_management.pipeline_runs.repos import PipelineRunRepository
from app.features.project_management.pipeline_runs.usecases.lifecycle import PipelineRunUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from sqlalchemy.exc import IntegrityError


class GitHubWebhookUseCase:
    def __init__(self, repo: GitHubWebhookRepository, runs: PipelineRunRepository, lifecycle: PipelineRunUseCase):
        self.repo = repo
        self.runs = runs
        self.lifecycle = lifecycle

    @staticmethod
    def verify_signature(secret: str, raw_body: bytes, signature: str | None) -> bool:
        expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return signature is not None and hmac.compare_digest(signature, expected)

    async def receive(self, delivery_id: str, event: str, raw_body: bytes, payload: dict[str, Any]) -> bool:
        repository = _repository(payload)
        try:
            async with AsyncTransaction() as session:
                await self.repo.create(
                    session,
                    GitHubWebhookDelivery(
                        delivery_id=delivery_id,
                        event=event,
                        repository=repository,
                        payload_digest=hashlib.sha256(raw_body).hexdigest(),
                    ),
                )
        except IntegrityError:
            # GitHub retries the same delivery ID; never re-run an external action.
            return False
        return True

    async def process(self, delivery_id: str, payload: dict[str, Any]) -> None:
        """Advance only the matching active run; periodic polling remains recovery."""
        try:
            repository = _repository(payload)
            if repository is None:
                return
            async with AsyncTransaction() as session:
                project = await self.repo.project_for_repository(session, repository)
                run = await self.runs.get_active(session, project.id) if project is not None else None
            if run is not None and _pull_number(payload) in (None, run.pull_number):
                await self.lifecycle.manual_advance(run.id, self.lifecycle.observer)
            await self._finish(delivery_id, "processed")
        except Exception:
            # Delivery endpoints must acknowledge authenticated GitHub events;
            # polling will recover transient processing failures.
            await self._finish(delivery_id, "failed", "Webhook processing failed")

    async def _finish(self, delivery_id: str, status: str, failure_detail: str | None = None) -> None:
        async with AsyncTransaction() as session:
            delivery = await self.repo.get(session, delivery_id)
            if delivery is not None:
                delivery.status = status
                delivery.processed_at = datetime.now(UTC)
                delivery.failure_detail = failure_detail
                await session.flush()


def _repository(payload: dict[str, Any]) -> str | None:
    value = payload.get("repository", {}).get("full_name")
    return value.lower() if isinstance(value, str) and value else None


def _pull_number(payload: dict[str, Any]) -> int | None:
    for key in ("pull_request", "issue"):
        number = payload.get(key, {}).get("number")
        if isinstance(number, int) and number > 0:
            return number
    return None
