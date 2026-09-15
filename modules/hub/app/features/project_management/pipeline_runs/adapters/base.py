from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.features.project_management.pipeline_runs.schemas import ImplementationRequest
from app.features.project_management.pipelines.services import PipelineObservationService


@dataclass(frozen=True)
class DeliveryTarget:
    connector_id: UUID
    repository: str
    pull_number: int


@dataclass(frozen=True)
class DeliveryReceipt:
    external_id: str
    posted_at: datetime
    url: str | None


@dataclass(frozen=True)
class AgentReply:
    external_id: str | None
    author: str
    replied_at: datetime
    body: str
    is_quota_limit: bool


class ExecutionAdapter(Protocol):
    """Delivers a request to an agent and reads its replies. The lifecycle owns run state and persistence."""

    key: str
    # How long a delivery may go without a push before the lifecycle retries it once.
    silent_timeout: timedelta
    silent_block_reason: str

    async def deliver(
        self,
        observer: PipelineObservationService,
        target: DeliveryTarget,
        request: ImplementationRequest,
        delivery_number: int,
        authorize: Callable[[], Awaitable[None]],
    ) -> DeliveryReceipt:
        """Return the already-made delivery with this number, or await ``authorize`` and then make it."""
        ...

    async def collect_replies(
        self, observer: PipelineObservationService, target: DeliveryTarget, posted_at: datetime | None
    ) -> list[AgentReply]:
        """Agent replies since the delivery; none before the delivery is confirmed."""
        ...
