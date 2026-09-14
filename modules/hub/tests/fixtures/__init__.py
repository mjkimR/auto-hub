"""
Centralized fixtures package for hub-specific testing resources.
"""

from tests.fixtures.connectors import (
    StaticCredentialKeyProvider,
    credential_key_provider,
)

__all__ = [
    "StaticCredentialKeyProvider",
    "credential_key_provider",
]
