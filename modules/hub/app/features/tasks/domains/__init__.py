"""Task domains — task-specific business logic that runs on top of the scheduler.

The top-level ``features/`` packages are the generic scheduler engine
(dispatchers, schedule_configs, ...). This package holds the *tasks* built on
that engine, one subpackage per domain.

Task autodiscovery imports this package; importing it in turn imports each
domain so its ``@task``-decorated entrypoints register. Add new task domains to
the imports below.
"""

from app.features.tasks.domains import appointment_chain, pipeline

__all__ = ["appointment_chain", "pipeline"]
