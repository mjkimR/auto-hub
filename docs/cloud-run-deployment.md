# Cloud Run Deployment Guide

This guide covers the end-to-end process of deploying Auto Hub to Google Cloud Run.  
The FastAPI backend (`modules/hub`) and Svelte 5 frontend (`modules/hub-ui`) are built and deployed together in a single consolidated container.

---

## ⚡ Quick Start (Using Helper Scripts)

Automated scripts are available under `docker/helper/`, allowing you to configure secrets and deploy with a single command:
- **GCS Staging Bucket**: The temporary source bucket for Cloud Build is always created in **`us-central1` (GCS 5GB Always Free tier)** and automatically cleaned up after the build.
- **Cloud Run & Artifact Registry**: Can be deployed to any region of your choice (default: Seoul `asia-northeast3`, etc.).

```bash
# [Case A: Using Aiven or External PostgreSQL (Recommended - 100% Free)]
# 1) Set up secrets
just setup-secrets -b "postgresql+asyncpg://avnadmin:<PASSWORD>@<HOST>:<PORT>/defaultdb?ssl=require"

# 2) Deploy to Cloud Run (runs directly without Cloud SQL flag)
just deploy-cloud-run

# [Case B: Using Google Cloud SQL]
# 1) Set up secrets
just setup-secrets -c "PROJECT:REGION:INSTANCE"

# 2) Deploy to Cloud Run
just deploy-cloud-run -c "PROJECT:REGION:INSTANCE"
```
*(To run each step manually, see steps 1 through 6 below.)*

---

## 1. Prerequisites (GCP Environment Setup)

### 1.1 Set GCP Project and Variables
```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="asia-northeast3" # Seoul region (or us-central1, etc.)
export SERVICE_NAME="auto-hub"
export REPO_NAME="auto-hub"
export DB_INSTANCE_NAME="auto-hub-db"

gcloud config set project "$PROJECT_ID"
```

### 1.2 Enable Required APIs
```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com
```

---

## 2. Database (Cloud SQL for PostgreSQL)

### 2.1 Create Cloud SQL Instance (If creating new)
> [!NOTE]
> If you already have an active PostgreSQL instance, skip this step and proceed to 2.2 to create the database and user.

```bash
gcloud sql instances create "$DB_INSTANCE_NAME" \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region="$REGION" \
  --root-password="<STRONG_ROOT_PASSWORD>"
```

### 2.2 Create Database and User
```bash
# Create database
gcloud sql databases create auto_hub --instance="$DB_INSTANCE_NAME"

# Create application user
gcloud sql users create hub_user \
  --instance="$DB_INSTANCE_NAME" \
  --password="<STRONG_USER_PASSWORD>"
```

---

## 3. Secret Manager Configuration

All Auto Hub secrets are stored as one JSON payload and injected through `APP_SECRETS_JSON`.
The setup helper generates the bundle and prints only the one-time plaintext API key needed for UI access:

```bash
just setup-secrets -- --project "$PROJECT_ID" --connection-name "$DB_CONNECTION_NAME"
```

The bundle contains `APP_SECRET_KEY`, `DATABASE_URL`, `GITHUB_WEBHOOK_SECRET`,
`CONNECTOR_CREDENTIAL_KEY`, and `CONNECTOR_CREDENTIAL_KEY_VERSION`. The app-common
environment loader expands these into normal environment variables at startup.

### 3.1 Database Connection URL (`DATABASE_URL`)
Cloud Run connects via Cloud SQL Unix Domain Socket (`/cloudsql/PROJECT:REGION:INSTANCE`):
```bash
# Retrieve Cloud SQL Connection Name
export DB_CONNECTION_NAME=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --format="value(connectionName)")

# Format: postgresql+asyncpg://<USER>:<PASSWORD>@/<DB_NAME>?host=/cloudsql/<CONNECTION_NAME>
export DATABASE_URL="postgresql+asyncpg://hub_user:<STRONG_USER_PASSWORD>@/auto_hub?host=/cloudsql/${DB_CONNECTION_NAME}"
# Pass DATABASE_URL to the setup helper, or use --database-url directly.
```

---

## 4. Service Account (IAM) Permissions

Grant Cloud SQL and Secret Manager access to the default Cloud Run Compute Service Account (or a custom dedicated service account).

```bash
export PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
export RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Secret Manager Secret Accessor
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUN_SA}" \
  --role="roles/secretmanager.secretAccessor"

# Cloud SQL Client
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUN_SA}" \
  --role="roles/cloudsql.client"
```

---

## 5. Container Build & Cloud Run Deployment

Even without a local Docker daemon, you can build directly in the cloud using **Google Cloud Build**.

### 5.1 Create Artifact Registry Repository
```bash
gcloud artifacts repositories create "$REPO_NAME" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Auto Hub docker repository"
```

### 5.2 Build & Push with Cloud Build
Run this from the project root directory:
```bash
export IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"

gcloud builds submit \
  --config=<(cat <<EOF
steps:
- name: 'gcr.io/cloud-builders/docker'
  env: ['DOCKER_BUILDKIT=1']
  args: ['build', '-f', 'docker/hub.Dockerfile', '-t', '${IMAGE_URI}', '.']
images:
- '${IMAGE_URI}'
timeout: '1200s'
EOF
) .
```

### 5.3 Deploy Cloud Run Service
```bash
gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE_URI" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8389 \
  --timeout=1200 \
  --memory=1Gi \
  --cpu=1 \
  --add-cloudsql-instances="$DB_CONNECTION_NAME" \
  --set-secrets="APP_SECRETS_JSON=auto-hub-secrets:latest"
```

Record the deployed Service URL output (e.g. `https://auto-hub-xxxx-du.a.run.app`):
```bash
export SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)")
echo "Auto Hub Service URL: $SERVICE_URL"
```

---

## 6. Register Cloud Scheduler (Periodic Trigger)

Set up Cloud Scheduler to invoke Auto Hub's observation and retry dispatcher ticks every minute.

```bash
gcloud scheduler jobs create http auto-hub-dispatcher-tick \
  --location="$REGION" \
  --schedule="* * * * *" \
  --uri="${SERVICE_URL}/api/v1/dispatchers/trigger" \
  --http-method=POST \
  --headers="X-API-Key=$(gcloud secrets versions access latest --secret=auto-hub-secrets | python3 -c 'import json,sys; print(json.load(sys.stdin)["APP_SECRET_KEY"])')" \
  --time-zone="UTC" \
  --attempt-deadline=300s
```

---

## 7. Post-Deployment Verification & Integration

1. **Verify Web Browser Access**
   - Navigate to `${SERVICE_URL}/` and verify that the Hub UI dashboard loads properly.
   - Enter the original plaintext API key supplied to `just setup-secrets` in the top-right corner or login modal to authenticate.
2. **Verify Swagger Docs**
   - Access `${SERVICE_URL}/docs` and verify the OpenAPI interactive documentation responds.
3. **Register GitHub Repository Webhook**

   **Method A: Automatic Registration via CLI (Recommended)**:
   Automatically retrieves Google Cloud Secrets and the Cloud Run URL to register or update the webhook on the target repository in seconds:
   ```bash
   just register-webhook <owner/repo>
   # Example: just register-webhook mjkimR/my-repo
   ```

   **Method B: Manual Registration via GitHub Web Console**:
   - Go to `Settings → Webhooks → Add webhook` on your target GitHub repository.
   - **Payload URL**: `${SERVICE_URL}/api/github/webhooks`
   - **Content type**: `application/json`
   - **Secret**: `GITHUB_WEBHOOK_SECRET` value from the `auto-hub-secrets` bundle
   - **Events**: Select `Let me select individual events` and check:
     - `Pull requests`
     - `Issue comments`
     - `Workflow runs`
   - After creating, check `Recent Deliveries` to confirm Ping delivery returns 200/202 OK.
4. **End-to-End Testing**
   - Enroll a project and pull request in the UI (or include `@auto-run` in the PR description / comments) to verify automated dispatch and CI monitoring progression.
