#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Setup Google Secret Manager secrets for Auto Hub
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-asia-northeast3}"
DB_CONNECTION_NAME="${DB_CONNECTION_NAME:-}"
DB_USER="${DB_USER:-hub_user}"
DB_PASSWORD="${DB_PASSWORD:-}"
DB_NAME="${DB_NAME:-auto_hub}"
DATABASE_URL="${DATABASE_URL:-}"
SA_NAME="${SA_NAME:-auto-hub-sa}"
RAW_APP_SECRET="${APP_SECRET:-${APP_SECRET_KEY:-}}"

usage() {
  cat <<EOF
Usage: $0 [OPTIONS]

Set up Secret Manager secrets required by Auto Hub.

Options:
  -p, --project PROJECT_ID     GCP Project ID (default: current gcloud project)
  -r, --region REGION          GCP Region (default: asia-northeast3)
  -s, --app-secret SECRET      Plaintext App Secret Key (will be SHA-256 hashed before storing)
  -a, --service-account NAME   Dedicated Service Account name (default: auto-hub-sa)
  -b, --database-url URL       Full PostgreSQL connection URL (e.g. Aiven/external DB)
  -c, --connection-name NAME   Cloud SQL Connection Name (PROJECT:REGION:INSTANCE)
  -u, --db-user USER           Database username (default: hub_user, for Cloud SQL)
  -w, --db-password PASSWORD   Database password (for Cloud SQL)
  -d, --db-name DBNAME         Database name (default: auto_hub)
  -h, --help                   Show this help message

Environment variables PROJECT_ID, REGION, APP_SECRET, DATABASE_URL, DB_CONNECTION_NAME, SA_NAME can also be used.
EOF
  exit 0
}



while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project) PROJECT_ID="$2"; shift 2 ;;
    -r|--region) REGION="$2"; shift 2 ;;
    -s|--app-secret) RAW_APP_SECRET="$2"; shift 2 ;;
    -a|--service-account) SA_NAME="$2"; shift 2 ;;
    -b|--database-url) DATABASE_URL="$2"; shift 2 ;;
    -c|--connection-name) DB_CONNECTION_NAME="$2"; shift 2 ;;
    -u|--db-user) DB_USER="$2"; shift 2 ;;
    -w|--db-password) DB_PASSWORD="$2"; shift 2 ;;
    -d|--db-name) DB_NAME="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done


if [[ -z "$PROJECT_ID" ]]; then
  echo "Error: GCP Project ID is required. Set via -p <project> or 'gcloud config set project <project>'." >&2
  exit 1
fi

echo "==> Configuring Secret Manager in project: $PROJECT_ID"

# Enable Secret Manager and IAM API if not enabled
gcloud services enable secretmanager.googleapis.com iam.googleapis.com --project="$PROJECT_ID"

# Helper function to compute SHA-256 hash
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

# Helper function to create secret if it does not exist, or add version if empty/forced
create_or_update_secret() {
  local secret_name="$1"
  local secret_val="$2"
  local force="${3:-false}"

  if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" >/dev/null 2>&1; then
    if [[ "$force" == "true" ]]; then
      echo "  - Updating secret '$secret_name' with new version..."
      echo -n "$secret_val" | gcloud secrets versions add "$secret_name" \
        --project="$PROJECT_ID" \
        --data-file=- >/dev/null
    else
      echo "  - Secret '$secret_name' already exists. Keeping existing secret."
    fi
  else
    echo "  - Creating secret '$secret_name'..."
    echo -n "$secret_val" | gcloud secrets create "$secret_name" \
      --project="$PROJECT_ID" \
      --replication-policy=automatic \
      --data-file=-
  fi
}

# 1. connector-credential-key (32 bytes AES key in base64)
KEY_VAL=$(openssl rand -base64 32)
create_or_update_secret "connector-credential-key" "$KEY_VAL"

# 2. auto-hub-app-secret (SHA-256 hashed secret for UI/API authentication)
if [[ -n "$RAW_APP_SECRET" ]]; then
  echo "  - Plaintext App Secret provided. Computing SHA-256 hash..."
  APP_SECRET_VAL=$(hash_sha256 "$RAW_APP_SECRET")
  create_or_update_secret "auto-hub-app-secret" "$APP_SECRET_VAL" "true"
else
  RANDOM_KEY=$(openssl rand -hex 32)
  APP_SECRET_VAL=$(hash_sha256 "$RANDOM_KEY")
  create_or_update_secret "auto-hub-app-secret" "$APP_SECRET_VAL"
fi

# 3. auto-hub-webhook-secret (20 bytes hex)
WEBHOOK_SECRET_VAL=$(openssl rand -hex 20)
create_or_update_secret "auto-hub-webhook-secret" "$WEBHOOK_SECRET_VAL"

# 4. auto-hub-database-url
if [[ -n "$DATABASE_URL" ]]; then
  # Normalize postgres:// or postgresql:// to postgresql+asyncpg://
  if [[ "$DATABASE_URL" =~ ^postgres:// ]]; then
    DATABASE_URL="postgresql+asyncpg://${DATABASE_URL#postgres://}"
  elif [[ "$DATABASE_URL" =~ ^postgresql:// ]]; then
    DATABASE_URL="postgresql+asyncpg://${DATABASE_URL#postgresql://}"
  fi
  # Normalize sslmode= to ssl= for asyncpg driver
  DATABASE_URL="${DATABASE_URL//sslmode=/ssl=}"
  echo "  - Storing provided DATABASE_URL..."
  if gcloud secrets describe "auto-hub-database-url" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo -n "$DATABASE_URL" | gcloud secrets versions add "auto-hub-database-url" --project="$PROJECT_ID" --data-file=- >/dev/null
    echo "    Updated 'auto-hub-database-url' with latest version."
  else
    create_or_update_secret "auto-hub-database-url" "$DATABASE_URL"
  fi
elif [[ -n "$DB_CONNECTION_NAME" ]]; then
  if [[ -z "$DB_PASSWORD" ]]; then
    read -rsp "Enter password for database user '$DB_USER': " DB_PASSWORD
    echo ""
  fi
  DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_CONNECTION_NAME}"
  create_or_update_secret "auto-hub-database-url" "$DATABASE_URL"
else
  echo "  - Notice: Neither --database-url nor --connection-name was specified."
  if ! gcloud secrets describe "auto-hub-database-url" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "    Please create 'auto-hub-database-url' manually or re-run with -b <URL> or -c <PROJECT:REGION:INSTANCE>."
  fi
fi


# 5. Create dedicated Service Account & grant secretAccessor role
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "==> Creating dedicated service account: $SA_NAME ($SA_EMAIL)..."
  gcloud iam service-accounts create "$SA_NAME" \
    --project="$PROJECT_ID" \
    --display-name="Auto Hub Service Account"
fi

echo "==> Granting roles/secretmanager.secretAccessor to $SA_EMAIL..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None >/dev/null

echo "==> Secret Manager setup completed successfully!"
echo "    Dedicated Service Account: $SA_EMAIL"
echo "    App Secret Key (Hashed for UI/API):"
gcloud secrets versions access latest --secret=auto-hub-app-secret --project="$PROJECT_ID"
echo ""

