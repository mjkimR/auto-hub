from typing import Protocol
from uuid import UUID

from app.features.pipeline_runs.schemas import ImplementationRequest
from pydantic import BaseModel


class DispatchObservation(BaseModel):
    correlation_marker: str
    external_correlation_id: str | None = None
    external_status: str | None = None
    conversation_url: str | None = None


class ExecutionProvider(Protocol):
    async def reconcile(self, linear_issue_id: UUID, correlation_marker: str) -> DispatchObservation | None: ...

    async def dispatch(self, linear_issue_id: UUID, body: str) -> DispatchObservation: ...


def build_codex_for_linear_comment(request: ImplementationRequest) -> str:
    """Build the stable comment payload; sending and reconciliation belong to an adapter."""
    return "\n".join(
        (
            f"@Codex implement this issue in {request.repository}.",
            f"Use `{request.base_branch}` as the base and `{request.head_branch}` as the working branch.",
            "Follow the repository instructions and run its required checks.",
            f"Correlation: `{request.correlation_marker}`",
        )
    )
