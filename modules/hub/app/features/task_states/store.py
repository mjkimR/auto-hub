"""Tiny read/write helpers over :class:`TaskState`.

Deliberately not a full repo/service stack — a stateful task only needs to load
its blob at the start of a tick and write it back at the end.
"""

from uuid import UUID

from app.features.task_states.models import TaskState
from sqlalchemy.ext.asyncio import AsyncSession


async def load(session: AsyncSession, config_id: UUID) -> dict | None:
    """Return the stored state blob for ``config_id``, or ``None`` if absent."""
    obj = await session.get(TaskState, config_id)
    return dict(obj.data) if obj is not None else None


async def upsert(session: AsyncSession, config_id: UUID, data: dict) -> None:
    """Insert or replace the state blob for ``config_id``."""
    obj = await session.get(TaskState, config_id)
    if obj is None:
        session.add(TaskState(config_id=config_id, data=data))
    else:
        obj.data = data  # reassign (JSON in-place mutation is not change-tracked)
    await session.flush()
