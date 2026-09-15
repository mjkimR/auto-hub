from datetime import datetime
from enum import StrEnum
from typing import ClassVar
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
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ExecutionAttemptKind(StrEnum):
    IMPLEMENTATION = "implementation"
    CI_FIX = "ci-fix"
    CONFLICT_FIX = "conflict-fix"
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
    PipelineRunState.BLOCKED,
)
ACTIVE_RUN_PREDICATE = text("state IN ('queued', 'dispatching', 'implementing', 'awaiting_ci', 'paused', 'blocked')")


class PipelineRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pipeline_runs"
    __mapper_args__: ClassVar[dict] = {"eager_defaults": True}
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_pipeline_runs_revision_positive"),
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

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    ai_catalog_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_catalogs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    # The GitHub binding captured at enrollment; a resume may adopt newer project settings only while it still holds.
    github_repository: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_connector_id: Mapped[UUID | None] = mapped_column(nullable=True)
    pull_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pull_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    pull_snapshot: Mapped[dict] = mapped_column(
        JSON_VARIANT, nullable=False, comment="Immutable pull request task specification captured at enrollment"
    )
    state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch: Mapped[str] = mapped_column(String(255), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_token: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    quota_block_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ExecutionAttempt(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "execution_attempts"
    __mapper_args__: ClassVar[dict] = {"eager_defaults": True}
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="ck_execution_attempts_number_positive"),
        Index("uq_execution_attempts_run_number", "pipeline_run_id", "attempt_number", unique=True),
    )

    pipeline_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
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


class ExecutionDelivery(Base, UUIDMixin, TimestampMixin):
    """A durable, reconcilable request to deliver one attempt through its catalog's adapter."""

    __tablename__ = "execution_deliveries"
    __table_args__ = (
        CheckConstraint("delivery_number >= 1", name="ck_execution_deliveries_number_positive"),
        Index("uq_execution_deliveries_attempt_number", "execution_attempt_id", "delivery_number", unique=True),
    )

    execution_attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delivery_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cause: Mapped[str] = mapped_column(String(30), nullable=False, default="initial")
    comment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExecutionReply(Base, UUIDMixin, TimestampMixin):
    """A trusted agent reply observed after a delivery.

    Replies are evidence, not a completion signal.  Keeping only a bounded,
    sanitized excerpt avoids retaining arbitrary GitHub comment bodies.
    """

    __tablename__ = "execution_replies"

    execution_attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    comment_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    replied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_quota_limit: Mapped[bool] = mapped_column(nullable=False, default=False)
