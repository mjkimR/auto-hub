from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TaskMeta:
    """Immutable metadata about the current task execution.

    Stored in a :class:`~contextvars.ContextVar` so that any code running
    within a dispatched task can retrieve it without explicit parameter passing.
    """

    config_id: UUID
    config_name: str
    run_id: UUID


_task_meta_var: ContextVar[TaskMeta | None] = ContextVar("task_meta", default=None)


@contextmanager
def task_context(*, config_id: UUID, config_name: str, run_id: UUID) -> Generator[TaskMeta]:
    """Set :class:`TaskMeta` for the duration of a ``with`` block.

    The previous context value is restored on exit (including on exception),
    preventing meta leakage between sequential task executions.

    Args:
        config_id: The UUID of the schedule config being executed.
        config_name: The human-readable name of the schedule config.
        run_id: The UUID of the dispatcher run.

    Yields:
        The newly created :class:`TaskMeta` instance.
    """
    meta = TaskMeta(config_id=config_id, config_name=config_name, run_id=run_id)
    token: Token[TaskMeta | None] = _task_meta_var.set(meta)
    try:
        yield meta
    finally:
        _task_meta_var.reset(token)


def get_task_meta() -> TaskMeta | None:
    """Retrieve the :class:`TaskMeta` for the current task context.

    Returns:
        The current :class:`TaskMeta`, or ``None`` if not inside a task context.
    """
    return _task_meta_var.get()
