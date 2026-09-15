# Auto Hub - Backend

This is the FastAPI backend for Auto Hub, built on the existing scheduler engine.

See the [Root README](../../README.md), [architecture](../../docs/architecture.md), and
[CI observation contract](../../docs/ci-contract.md) for current scope and development direction.

## Development

Run commands from the repository root using the [justfile](../../justfile).
See [development and operations](../../docs/development.md) for verification and scheduler behavior.

## Connector credential encryption

Connector credentials are encrypted with AES-256-GCM before they are stored in the database. The base64-encoded
32-byte key is supplied as `CONNECTOR_CREDENTIAL_KEY`, normally as one field in the application's `APP_SECRETS_JSON`
bundle. Generate it with `openssl rand -base64 32`. The `CONNECTOR_CREDENTIAL_KEY_VERSION` label remains stored with
each encrypted row for future re-encryption support; changing the key currently requires re-encrypting the stored
connector credentials before removing the old key.
