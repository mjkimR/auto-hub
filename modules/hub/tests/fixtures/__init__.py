"""
Centralized fixtures package.
Import all fixtures from this package for easy access.
"""

from tests.fixtures.clients import (
    AsyncClientWithJson,
    app_fixture,
    client_fixture,
)
from tests.fixtures.db import (
    async_engine,
    db_url,
    session_fixture,
    setup_database,
)

__all__ = [
    # Database fixtures
    "db_url",
    "setup_database",
    "async_engine",
    "session_fixture",
    # Client fixtures
    "AsyncClientWithJson",
    "app_fixture",
    "client_fixture",
    # Auth fixtures (add auth fixtures here when available)
]
