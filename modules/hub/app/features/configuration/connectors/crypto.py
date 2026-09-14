import asyncio
import base64
import binascii
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Protocol
from uuid import UUID

import orjson
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends
from google.cloud import secretmanager_v1
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_AES_256_KEY_BYTES = 32
_GCM_NONCE_BYTES = 12
_AAD_VERSION = "v1"


class ConnectorCryptoConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    CONNECTOR_CREDENTIAL_KEY_SECRET: str = Field(
        ...,
        description=(
            "Secret Manager resource without a version, for example "
            "projects/my-project/secrets/connector-credential-key"
        ),
    )
    CONNECTOR_CREDENTIAL_KEY_VERSION: str = Field(
        "1",
        description="Secret Manager version containing the current base64-encoded 32-byte AES key",
    )


@lru_cache
def get_connector_crypto_config() -> ConnectorCryptoConfig:
    return ConnectorCryptoConfig(**{})


class CredentialKeyProvider(Protocol):
    @property
    def current_version(self) -> str: ...

    async def get_key(self, version: str) -> bytes: ...


class SecretManagerCredentialKeyProvider:
    def __init__(self, config: Annotated[ConnectorCryptoConfig, Depends(get_connector_crypto_config)]):
        self._secret_resource = config.CONNECTOR_CREDENTIAL_KEY_SECRET.rstrip("/")
        self._current_version = config.CONNECTOR_CREDENTIAL_KEY_VERSION
        self._client: secretmanager_v1.SecretManagerServiceAsyncClient | None = None
        self._keys: dict[str, bytes] = {}
        self._load_lock = asyncio.Lock()

    @property
    def current_version(self) -> str:
        return self._current_version

    async def get_key(self, version: str) -> bytes:
        if key := self._keys.get(version):
            return key

        async with self._load_lock:
            if key := self._keys.get(version):
                return key

            if self._client is None:
                self._client = secretmanager_v1.SecretManagerServiceAsyncClient()

            response = await self._client.access_secret_version(
                request={"name": f"{self._secret_resource}/versions/{version}"}
            )
            key = self._decode_key(response.payload.data)
            self._keys[version] = key
            return key

    @staticmethod
    def _decode_key(value: bytes) -> bytes:
        try:
            key = base64.b64decode(value.strip(), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Connector credential key must be valid base64") from exc

        if len(key) != _AES_256_KEY_BYTES:
            raise ValueError("Connector credential key must decode to exactly 32 bytes")
        return key


@lru_cache
def get_credential_key_provider() -> CredentialKeyProvider:
    """Return one cached provider so each process reads a key version only once."""
    return SecretManagerCredentialKeyProvider(get_connector_crypto_config())


@dataclass(frozen=True)
class EncryptedCredentials:
    ciphertext: bytes
    nonce: bytes
    key_version: str


class CredentialDecryptionError(ValueError):
    pass


class ConnectorCredentialCipher:
    def __init__(self, key_provider: Annotated[CredentialKeyProvider, Depends(get_credential_key_provider)]):
        self._key_provider = key_provider

    async def encrypt(
        self,
        connector_id: UUID,
        provider: str,
        credentials: dict,
    ) -> EncryptedCredentials:
        key_version = self._key_provider.current_version
        key = await self._key_provider.get_key(key_version)
        nonce = os.urandom(_GCM_NONCE_BYTES)
        plaintext = orjson.dumps(credentials, option=orjson.OPT_SORT_KEYS)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, self._aad(connector_id, provider))
        return EncryptedCredentials(ciphertext=ciphertext, nonce=nonce, key_version=key_version)

    async def decrypt(
        self,
        connector_id: UUID,
        provider: str,
        encrypted: EncryptedCredentials,
    ) -> dict:
        key = await self._key_provider.get_key(encrypted.key_version)
        try:
            plaintext = AESGCM(key).decrypt(
                encrypted.nonce,
                encrypted.ciphertext,
                self._aad(connector_id, provider),
            )
        except InvalidTag as exc:
            raise CredentialDecryptionError("Connector credentials could not be authenticated") from exc

        value = orjson.loads(plaintext)
        if not isinstance(value, dict):
            raise CredentialDecryptionError("Connector credentials must decode to an object")
        return value

    @staticmethod
    def _aad(connector_id: UUID, provider: str) -> bytes:
        return f"connector:{connector_id}:{provider}:{_AAD_VERSION}".encode()
