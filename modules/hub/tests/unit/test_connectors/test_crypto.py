import os
import uuid
from base64 import b64encode

import pytest
from app.features.connectors.crypto import (
    ConnectorCredentialCipher,
    CredentialDecryptionError,
    EncryptedCredentials,
    SecretManagerCredentialKeyProvider,
)

from tests.fixtures.connectors import StaticCredentialKeyProvider


@pytest.mark.unit
class TestConnectorCredentialCipher:
    async def test_secret_manager_key_must_decode_to_32_bytes(self):
        key = bytes(range(32))

        assert SecretManagerCredentialKeyProvider._decode_key(b64encode(key)) == key

        with pytest.raises(ValueError, match="exactly 32 bytes"):
            SecretManagerCredentialKeyProvider._decode_key(b64encode(b"too-short"))

    async def test_encrypt_and_decrypt_credentials(self):
        cipher = ConnectorCredentialCipher(StaticCredentialKeyProvider(bytes(range(32))))
        connector_id = uuid.uuid4()
        credentials = {"token": "top-secret", "private_key": "private-key-data"}

        encrypted = await cipher.encrypt(connector_id, "github", credentials)
        decrypted = await cipher.decrypt(connector_id, "github", encrypted)

        assert decrypted == credentials
        assert b"top-secret" not in encrypted.ciphertext
        assert len(encrypted.nonce) == 12
        assert encrypted.key_version == "test-v1"

    async def test_encrypt_uses_unique_nonce_for_each_record(self):
        cipher = ConnectorCredentialCipher(StaticCredentialKeyProvider(bytes(range(32))))
        connector_id = uuid.uuid4()

        first = await cipher.encrypt(connector_id, "github", {"token": "same-value"})
        second = await cipher.encrypt(connector_id, "github", {"token": "same-value"})

        assert first.nonce != second.nonce
        assert first.ciphertext != second.ciphertext

    async def test_decrypt_rejects_tampered_ciphertext(self):
        cipher = ConnectorCredentialCipher(StaticCredentialKeyProvider(os.urandom(32)))
        connector_id = uuid.uuid4()
        encrypted = await cipher.encrypt(connector_id, "github", {"token": "secret"})
        tampered = EncryptedCredentials(
            ciphertext=encrypted.ciphertext[:-1] + bytes([encrypted.ciphertext[-1] ^ 1]),
            nonce=encrypted.nonce,
            key_version=encrypted.key_version,
        )

        with pytest.raises(CredentialDecryptionError):
            await cipher.decrypt(connector_id, "github", tampered)

    async def test_decrypt_binds_credentials_to_connector_and_provider(self):
        cipher = ConnectorCredentialCipher(StaticCredentialKeyProvider(os.urandom(32)))
        encrypted = await cipher.encrypt(uuid.uuid4(), "github", {"token": "secret"})

        with pytest.raises(CredentialDecryptionError):
            await cipher.decrypt(uuid.uuid4(), "github", encrypted)
