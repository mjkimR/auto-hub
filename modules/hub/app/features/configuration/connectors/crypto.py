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
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_AES_256_KEY_BYTES = 32
_GCM_NONCE_BYTES = 12
_AAD_VERSION = "v1"


class ConnectorCryptoConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    CONNECTOR_CREDENTIAL_KEY: SecretStr = Field(
        ...,
        description="Base64-encoded 32-byte AES key used to encrypt connector credentials",
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


class EnvironmentCredentialKeyProvider:
    def __init__(self, config: Annotated[ConnectorCryptoConfig, Depends(get_connector_crypto_config)]):
        self._current_version = config.CONNECTOR_CREDENTIAL_KEY_VERSION
        self._key = self._decode_key(config.CONNECTOR_CREDENTIAL_KEY.get_secret_value().encode())

    @property
    def current_version(self) -> str:
        return self._current_version

    async def get_key(self, version: str) -> bytes:
        if version != self._current_version:
            raise ValueError(f"Unsupported connector credential key version: {version}")
        return self._key

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
    return EnvironmentCredentialKeyProvider(get_connector_crypto_config())


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
