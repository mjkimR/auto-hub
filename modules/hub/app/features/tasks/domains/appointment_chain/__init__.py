"""Appointment-chain task domain.

A self-perpetuating chain of recurring appointments on a calendar (see
``task.py`` / ``reconcile.py``). Importing this package registers the
``calendar.reconcile_chain`` task.
"""

from app.features.tasks.domains.appointment_chain.task import reconcile_chain_task, run_reconcile

__all__ = ["reconcile_chain_task", "run_reconcile"]
