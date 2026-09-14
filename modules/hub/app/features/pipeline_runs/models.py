from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column


class PipelineRunState(StrEnum):
    QUEUED = "queued"
    DISPATCHING = "dispatching"
    IMPLEMENTING = "implementing"
    AWAITING_CI = "awaiting_ci"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ExecutionAttemptKind(StrEnum):
    IMPLEMENTATION = "implementation"
    REVISION = "revision"


class ExecutionAttemptState(StrEnum):
    PLANNED = "planned"
    DISPATCHING = "dispatching"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"


ACTIVE_RUN_STATES = (
    PipelineRunState.QUEUED,
    PipelineRunState.DISPATCHING,
    PipelineRunState.IMPLEMENTING,
    PipelineRunState.AWAITING_CI,
    PipelineRunState.PAUSED,
)
ACTIVE_RUN_PREDICATE = text("state IN ('queued', 'dispatching', 'implementing', 'awaiting_ci', 'paused')")


class PipelineRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_pipeline_runs_revision_positive"),
        Index(
            "uq_pipeline_runs_active_project",
            "project_id",
            unique=True,
            postgresql_where=ACTIVE_RUN_PREDICATE,
            sqlite_where=ACTIVE_RUN_PREDICATE,
        ),
        Index(
            "uq_pipeline_runs_active_pull",
            "project_id",
            "pull_number",
            unique=True,
            postgresql_where=ACTIVE_RUN_PREDICATE,
            sqlite_where=ACTIVE_RUN_PREDICATE,
        ),
        Index("ix_pipeline_runs_project_created", "project_id", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(ForeignKey("project_connections.id", ondelete="RESTRICT"), nullable=False)
    project_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    pull_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pull_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    pull_snapshot: Mapped[dict] = mapped_column(
        JSON_VARIANT, nullable=False, comment="Immutable pull request task specification captured at enrollment"
    )
    state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch: Mapped[str] = mapped_column(String(255), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_token: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class ExecutionAttempt(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "execution_attempts"
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="ck_execution_attempts_number_positive"),
        Index("uq_execution_attempts_run_number", "pipeline_run_id", "attempt_number", unique=True),
    )

    pipeline_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    request_snapshot: Mapped[dict] = mapped_column(JSON_VARIANT, nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(nullable=False, unique=True)
    external_correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    external_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    conversation_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
