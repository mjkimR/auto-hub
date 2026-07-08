from uuid import UUID

from app.common.database import JSON_VARIANT
from app_base.base.models.mixin import Base, TimestampMixin
from sqlalchemy import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column


class TaskState(Base, TimestampMixin):
    """Durable, opaque state for a stateful task, keyed by its ScheduleConfig id.

    Static configuration for a task lives in ``ScheduleConfig.payload`` and is
    read fresh each tick. Anything a task must *remember* between ticks (a
    reconcile loop's cursor, the last-notified date, ...) lives here instead —
    the dispatcher passes only a snapshot of the payload, so there is no
    write-back path through it.

    ``data`` is an opaque JSON blob owned entirely by the task; this store does
    not interpret it.
    """

    __tablename__ = "task_states"

    config_id: Mapped[UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        primary_key=True,
        comment="ScheduleConfig id this state belongs to (from the task execution context).",
    )
    data: Mapped[dict] = mapped_column(
        JSON_VARIANT, nullable=False, default=dict, comment="Opaque, task-owned state blob."
    )
