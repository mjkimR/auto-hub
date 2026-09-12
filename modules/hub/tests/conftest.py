"""
Main conftest.py for test configuration and shared fixtures.

Integrates app-testing-base standard test plugins and provides
hub-specific overrides and configuration.
"""

import logging
import os

import pytest

pytest_plugins = [
    "app_testing_base.plugin",
    "tests.fixtures.connectors",
    "tests.fixtures.data_factory",
]

# Set the default test secret key to prevent authentication misconfiguration issues during tests.
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key")

# Pin the in-memory calendar backend. Overridden, not defaulted: a developer's .env may set
# CALENDAR_BACKEND=google, and the suite must never reach a live calendar.
os.environ["CALENDAR_BACKEND"] = "fake"

# Configure logging - reduce noise from SQLAlchemy and httpx
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


@pytest.fixture
def client_headers() -> dict[str, str]:
    """Default headers for test client including API key authentication."""
    from app.common.config import get_auth_config

    try:
        api_key = get_auth_config().APP_SECRET_KEY.get_secret_value()
    except Exception:
        api_key = "test"

    return {
        "X-API-Key": api_key,
    }


@pytest.fixture
def app(credential_key_provider):
    """Create FastAPI app with hub-specific credential overrides."""
    from app.features.connectors.crypto import get_credential_key_provider
    from app.main import create_app

    application = create_app()
    application.dependency_overrides[get_credential_key_provider] = lambda: credential_key_provider
    yield application
    application.dependency_overrides.clear()
