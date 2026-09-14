#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Cloud Run deployment script for Auto Hub
# Builds unified container (UI + Backend) with Cloud Build and deploys to Cloud Run
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-asia-northeast3}"
SERVICE_NAME="${SERVICE_NAME:-auto-hub}"
REPO_NAME="${REPO_NAME:-auto-hub}"
DB_CONNECTION_NAME="${DB_CONNECTION_NAME:-}"
TAG="${TAG:-latest}"
SETUP_SCHEDULER="${SETUP_SCHEDULER:-true}"
KEEP_VERSIONS="${KEEP_VERSIONS:-2}"
SA_NAME="${SA_NAME:-auto-hub-sa}"

usage() {
  cat <<EOF
Usage: $0 [OPTIONS]

Build and deploy Auto Hub to Google Cloud Run using Cloud Build.

Options:
  -p, --project PROJECT_ID     GCP Project ID (default: current gcloud project)
  -r, --region REGION          GCP Region (default: asia-northeast3)
  -s, --service NAME           Cloud Run service name (default: auto-hub)
  -a, --service-account NAME   Dedicated Service Account name (default: auto-hub-sa)
  -c, --connection-name NAME   Cloud SQL Connection Name (PROJECT:REGION:INSTANCE)
  -t, --tag TAG                Image tag (default: latest)
  -k, --keep-versions N        Number of image versions to retain (default: 2)
  --no-scheduler               Skip Cloud Scheduler job registration
  -h, --help                   Show this help message

Environment variables PROJECT_ID, REGION, SERVICE_NAME, DB_CONNECTION_NAME, KEEP_VERSIONS, SA_NAME can also be used.
EOF
  exit 0
}


while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project) PROJECT_ID="$2"; shift 2 ;;
    -r|--region) REGION="$2"; shift 2 ;;
    -s|--service) SERVICE_NAME="$2"; shift 2 ;;
    -a|--service-account) SA_NAME="$2"; shift 2 ;;
    -c|--connection-name) DB_CONNECTION_NAME="$2"; shift 2 ;;
    -t|--tag) TAG="$2"; shift 2 ;;
    -k|--keep-versions) KEEP_VERSIONS="$2"; shift 2 ;;
    --no-scheduler) SETUP_SCHEDULER="false"; shift 1 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done



if [[ -z "$PROJECT_ID" ]]; then
  echo "Error: GCP Project ID is required. Set via -p <project> or 'gcloud config set project <project>'." >&2
  exit 1
fi

echo "==> Deploying Auto Hub to Cloud Run"
echo "    Project : $PROJECT_ID"
echo "    Region  : $REGION"
echo "    Service : $SERVICE_NAME"

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  --project="$PROJECT_ID"

# 1. Ensure Artifact Registry repository exists
if ! gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "==> Creating Artifact Registry repository '$REPO_NAME' in $REGION..."
  gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Auto Hub docker repository" \
    --project="$PROJECT_ID"
fi

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${TAG}"

# 2. Ensure Cloud Build GCS staging bucket is fixed to us-central1 (Always Free Tier)
GCS_STAGING_REGION="us-central1"
CLOUDBUILD_BUCKET="gs://${PROJECT_ID}-cloudbuild-us"

if ! gcloud storage buckets describe "$CLOUDBUILD_BUCKET" >/dev/null 2>&1; then
  echo "==> Creating GCS staging bucket in $GCS_STAGING_REGION (Free Tier): $CLOUDBUILD_BUCKET..."
  gcloud storage buckets create "$CLOUDBUILD_BUCKET" \
    --location="$GCS_STAGING_REGION" \
    --project="$PROJECT_ID" \
    --uniform-bucket-level-access 2>/dev/null || true
fi

# 3. Build image via Cloud Build
echo "==> Submitting build to Google Cloud Build (Image: $IMAGE_URI)..."
cd "$ROOT_DIR"

gcloud builds submit \
  --project="$PROJECT_ID" \
  --gcs-source-staging-dir="${CLOUDBUILD_BUCKET}/source" \
  --gcs-log-dir="${CLOUDBUILD_BUCKET}/logs" \
  --config=<(cat <<EOF
steps:
- name: 'gcr.io/cloud-builders/docker'
  env: ['DOCKER_BUILDKIT=1']
  args: ['build', '-f', 'docker/hub.Dockerfile', '-t', '${IMAGE_URI}', '.']
images:
- '${IMAGE_URI}'
timeout: '1800s'
EOF
) .


# 4. Cloud Run Deploy
echo "==> Deploying container to Cloud Run..."

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

DEPLOY_ARGS=(
  "$SERVICE_NAME"
  --image="$IMAGE_URI"
  --region="$REGION"
  --project="$PROJECT_ID"
  --platform=managed
  --allow-unauthenticated
  --port=8389
  --timeout=1200
  --memory=1Gi
  --cpu=1
  --service-account="$SA_EMAIL"
  --set-env-vars="CONNECTOR_CREDENTIAL_KEY_SECRET=projects/${PROJECT_ID}/secrets/connector-credential-key,CONNECTOR_CREDENTIAL_KEY_VERSION=1"
  --set-secrets="APP_SECRET_KEY=auto-hub-app-secret:latest,DATABASE_URL=auto-hub-database-url:latest,GITHUB_WEBHOOK_SECRET=auto-hub-webhook-secret:latest"
)

if [[ -n "$DB_CONNECTION_NAME" ]]; then
  DEPLOY_ARGS+=(--add-cloudsql-instances="$DB_CONNECTION_NAME")
fi


gcloud run deploy "${DEPLOY_ARGS[@]}"

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")
echo "==> Service deployed successfully!"
echo "    URL: $SERVICE_URL"

# 4. Configure Cloud Scheduler (1-minute tick trigger)
if [[ "$SETUP_SCHEDULER" == "true" ]]; then
  JOB_NAME="${SERVICE_NAME}-dispatcher-tick"
  echo "==> Configuring Cloud Scheduler job: $JOB_NAME..."

  APP_SECRET=$(gcloud secrets versions access latest --secret=auto-hub-app-secret --project="$PROJECT_ID" 2>/dev/null || true)
  if [[ -n "$APP_SECRET" ]]; then
    if gcloud scheduler jobs describe "$JOB_NAME" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
      gcloud scheduler jobs update http "$JOB_NAME" \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        --schedule="* * * * *" \
        --uri="${SERVICE_URL}/api/v1/dispatchers/trigger" \
        --http-method=POST \
        --update-headers="X-API-Key=${APP_SECRET}" \
        --time-zone="UTC" \
        --attempt-deadline=300s >/dev/null
      echo "  - Updated existing Cloud Scheduler job."
    else
      gcloud scheduler jobs create http "$JOB_NAME" \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        --schedule="* * * * *" \
        --uri="${SERVICE_URL}/api/v1/dispatchers/trigger" \
        --http-method=POST \
        --headers="X-API-Key=${APP_SECRET}" \
        --time-zone="UTC" \
        --attempt-deadline=300s >/dev/null
      echo "  - Created new Cloud Scheduler job."
    fi
  else
    echo "  - Warning: auto-hub-app-secret not found. Cloud Scheduler job skipped."
  fi
fi

# 5. Clean up old images in Artifact Registry (keep only latest N versions)
echo "==> Cleaning up older images in Artifact Registry (keeping latest ${KEEP_VERSIONS})..."
OLD_DIGESTS=$(gcloud artifacts docker images list "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}" \
  --project="$PROJECT_ID" \
  --sort-by="~CREATE_TIME" \
  --format="value(DIGEST)" 2>/dev/null | sed -e "1,${KEEP_VERSIONS}d" || true)

if [[ -n "$OLD_DIGESTS" ]]; then
  for digest in $OLD_DIGESTS; do
    echo "  - Removing old image version: $digest"
    gcloud artifacts docker images delete \
      "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}@${digest}" \
      --project="$PROJECT_ID" \
      --delete-tags \
      --quiet 2>/dev/null || true
  done
  echo "  - Old images cleaned up."
else
  echo "  - No old images to clean up (total versions <= ${KEEP_VERSIONS})."
fi

# 6. Clean up temporary Cloud Build source tarballs
if gcloud storage buckets describe "$CLOUDBUILD_BUCKET" >/dev/null 2>&1; then
  echo "==> Cleaning up temporary Cloud Build staging files in $CLOUDBUILD_BUCKET..."
  gcloud storage rm "${CLOUDBUILD_BUCKET}/source/**" --recursive --quiet 2>/dev/null || true
  gcloud storage rm "${CLOUDBUILD_BUCKET}/logs/**" --recursive --quiet 2>/dev/null || true
fi


echo ""
echo "================================================================="
echo " Auto Hub is live at: $SERVICE_URL"
echo " - Health check: curl $SERVICE_URL/api/health"
echo " - UI Access   : Open $SERVICE_URL in browser"
echo " - Webhook URL : $SERVICE_URL/api/v1/webhooks/github"
echo "================================================================="

