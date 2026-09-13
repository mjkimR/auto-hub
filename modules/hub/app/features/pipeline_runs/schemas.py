from datetime import datetime
from typing import Literal
from uuid import UUID

from app.features.pipeline_runs.models import ExecutionAttemptKind, ExecutionAttemptState, PipelineRunState
from app.features.projects.schemas import ActionableIssueSelection, LinearIssue
from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class PipelineRunRead(UUIDSchemaMixin, TimestampSchemaMixin):
    model_config = ConfigDict(from_attributes=True)

    project_id: UUID
    project_revision: int
    linear_issue_id: UUID
    linear_issue_identifier: str
    linear_issue_snapshot: LinearIssue
    state: PipelineRunState
    pause_reason: str | None
    branch: str
    pull_number: int | None
    pull_url: str | None
    revision: int
    lease_owner: str | None
    lease_expires_at: datetime | None


class ExecutionAttemptRead(UUIDSchemaMixin, TimestampSchemaMixin):
    model_config = ConfigDict(from_attributes=True)

    pipeline_run_id: UUID
    attempt_number: int = Field(ge=1)
    kind: ExecutionAttemptKind
    state: ExecutionAttemptState
    request_snapshot: dict
    request_digest: str
    idempotency_key: UUID
    external_correlation_id: str | None
    external_status: str | None
    conversation_url: str | None
    started_at: datetime | None
    finished_at: datetime | None
    failure_code: str | None
    failure_detail: str | None


class PipelineRunList(BaseModel):
    items: list[PipelineRunRead]
    total_count: int


class ExecutionAttemptList(BaseModel):
    items: list[ExecutionAttemptRead]
    total_count: int


class PipelineRunAcquisition(BaseModel):
    run: PipelineRunRead | None
    created: bool
    selection: ActionableIssueSelection | None = None


class LeaseRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=255)
    ttl_seconds: int = Field(default=60, ge=15, le=900)


class LeaseCredential(BaseModel):
    owner: str = Field(min_length=1, max_length=255)
    token: UUID


class LeaseMutation(LeaseCredential):
    ttl_seconds: int = Field(default=60, ge=15, le=900)


class LeaseGrant(BaseModel):
    run_id: UUID
    owner: str
    token: UUID
    expires_at: datetime
    run_revision: int


class ImplementationRequest(BaseModel):
    version: Literal[1] = 1
    correlation_marker: str
    repository: str
    base_branch: str
    head_branch: str
    issue: LinearIssue
    instructions: str


class PrepareImplementationAttempt(LeaseCredential):
    expected_run_revision: int = Field(ge=1)
    base_branch: str = Field(min_length=1, max_length=255, pattern=r"^[^\s~^:?*\\\[]+$")


class PreparedImplementationAttempt(BaseModel):
    attempt: ExecutionAttemptRead
    request: ImplementationRequest
    run_revision: int
    created: bool


class PauseRunRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AttachPRRequest(BaseModel):
    pull_number: int = Field(gt=0)
    pull_url: str | None = Field(default=None, max_length=1000)


class CompleteAttemptRequest(BaseModel):
    status: Literal["completed", "failed"]
    failure_code: str | None = Field(default=None, max_length=100)
    failure_detail: str | None = Field(default=None, max_length=2000)
