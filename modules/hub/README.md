# Scheduler Manager - Hub Module

This is the main backend service for the Scheduler Manager.

For detailed documentation on features, architecture, and local development, please refer to the [Root README](../../README.md).

## Quick Start (from this directory)

```bash
# Run migrations
alembic upgrade head

# Start server
fastapi dev app/main.py
```

## Connector credential encryption

Connector credentials are encrypted with AES-256-GCM before they are stored in the database. The 32-byte master key
is stored as base64 text in Google Secret Manager; never place the key itself in `.env`.

Create the secret and its first version:

```bash
openssl rand -base64 32 | gcloud secrets create connector-credential-key \
  --replication-policy=automatic \
  --data-file=-
```

Configure the application with the secret resource and an explicit version:

```dotenv
CONNECTOR_CREDENTIAL_KEY_SECRET=projects/PROJECT_ID/secrets/connector-credential-key
CONNECTOR_CREDENTIAL_KEY_VERSION=1
```

The runtime service account needs `roles/secretmanager.secretAccessor` on this secret. A key version is cached in
process memory after its first use, and each database row records the version that encrypted it so keys can be rotated
without invalidating existing credentials.
