#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Update Auto Hub API Key across Secret Manager, Cloud Scheduler, and Cloud Run
# ─────────────────────────────────────────────────────────────────────────────

KEY="${1:-}"

if [[ -z "$KEY" ]]; then
  read -rsp "Enter new secret key: " KEY
  echo ""
fi

if [[ -z "$KEY" ]]; then
  echo "Error: Secret key cannot be empty." >&2
  exit 1
fi

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-asia-northeast3}"
SERVICE_NAME="${SERVICE_NAME:-auto-hub}"
JOB_NAME="${SERVICE_NAME}-dispatcher-tick"

if [[ -z "$PROJECT_ID" ]]; then
  echo "Error: GCP Project ID is required. Set via 'gcloud config set project <project>'." >&2
  exit 1
fi

hash_sha256() {
  local val="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    echo -n "$val" | sha256sum | awk '{print $1}'
  elif command -v openssl >/dev/null 2>&1; then
    echo -n "$val" | openssl dgst -sha256 | awk '{print $NF}'
  else
    python3 -c "import hashlib, sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" "$val"
  fi
}

HASHED_KEY=$(hash_sha256 "$KEY")
echo "==> Updating API key for project: $PROJECT_ID (Region: $REGION)"

# 1. Update Secret Manager
echo "==> [1/4] Updating Google Secret Manager ('auto-hub-secrets')..."
CURRENT_JSON=$(gcloud secrets versions access latest --secret=auto-hub-secrets --project="$PROJECT_ID" 2>/dev/null || true)
if [[ -z "$CURRENT_JSON" ]]; then
  echo "Error: auto-hub-secrets does not exist. Run 'just setup-secrets' first." >&2
  exit 1
fi
UPDATED_JSON=$(CURRENT_JSON="$CURRENT_JSON" HASHED_KEY="$HASHED_KEY" python3 -c 'import json, os; value=json.loads(os.environ["CURRENT_JSON"]); value["APP_SECRET_KEY"]=os.environ["HASHED_KEY"]; print(json.dumps(value, separators=(",", ":")))')
echo -n "$UPDATED_JSON" | gcloud secrets versions add "auto-hub-secrets" \
  --project="$PROJECT_ID" --data-file=- >/dev/null
echo "  ✓ Added new version to 'auto-hub-secrets'."

# 2. Update Cloud Scheduler trigger header
echo "==> [2/4] Updating Cloud Scheduler job ('$JOB_NAME')..."
if gcloud scheduler jobs describe "$JOB_NAME" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$JOB_NAME" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --update-headers="X-API-Key=${HASHED_KEY}" >/dev/null
  echo "  ✓ Updated Cloud Scheduler header with new key."
else
  echo "  - Notice: Cloud Scheduler job '$JOB_NAME' not found in $REGION. (Run 'just deploy-cloud-run' to create it)"
fi

# 3. Update Cloud Run service to reload latest secret
echo "==> [3/4] Updating Cloud Run service ('$SERVICE_NAME')..."
if gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud run services update "$SERVICE_NAME" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --update-secrets="APP_SECRETS_JSON=auto-hub-secrets:latest" >/dev/null
  echo "  ✓ Deployed new revision to reload latest secret."
else
  echo "  - Notice: Cloud Run service '$SERVICE_NAME' not found in $REGION. (Run 'just deploy-cloud-run' to deploy it)"
fi

# 4. Update local .env if present
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/modules/hub/.env"
echo "==> [4/4] Checking local .env file..."
if [[ -f "$ENV_FILE" ]]; then
  if grep -q "^APP_SECRET_KEY=" "$ENV_FILE"; then
    # An attached backup suffix is accepted by both BSD (macOS) and GNU sed.
    sed -i.bak "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=${HASHED_KEY}|" "$ENV_FILE"
    rm -f "${ENV_FILE}.bak"
    echo "  ✓ Updated APP_SECRET_KEY in $ENV_FILE."
  else
    echo "APP_SECRET_KEY=${HASHED_KEY}" >> "$ENV_FILE"
    echo "  ✓ Appended APP_SECRET_KEY to $ENV_FILE."
  fi
else
  echo "  - Notice: $ENV_FILE does not exist. Skipping local update."
fi

echo ""
echo "==> API Key update complete!"
echo "    Hashed Key for UI/API: $HASHED_KEY"
