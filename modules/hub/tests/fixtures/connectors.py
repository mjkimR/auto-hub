import os

import pytest


class StaticCredentialKeyProvider:
    current_version = "test-v1"

    def __init__(self, key: bytes | None = None):
        self.key = key or os.urandom(32)

    async def get_key(self, version: str) -> bytes:
        if version != self.current_version:
            raise KeyError(version)
        return self.key


@pytest.fixture
def credential_key_provider():
    return StaticCredentialKeyProvider()
