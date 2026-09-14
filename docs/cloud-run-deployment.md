# Cloud Run Deployment Guide

Auto Hub를 Google Cloud Run에 배포하는 전체 절차 가이드입니다.  
FastAPI 백엔드(`modules/hub`)와 Svelte 5 프론트엔드(`modules/hub-ui`)가 단일 컨테이너로 통합 빌드되어 배포됩니다.

---

## ⚡ 빠른 시작 (Helper 스크립트 사용)

`docker/helper/`에 자동화 스크립트가 준비되어 있어 명령 한 줄로 시크릿 설정 및 배포가 가능합니다.
- **GCS Staging Bucket**: Cloud Build 임시 소스 버킷은 항상 **`us-central1` (GCS 5GB 상시 무료 티어)**에 고정 생성되며 빌드 후 자동 청소됩니다.
- **Cloud Run & Artifact Registry**: 원하는 리전(기본값: 서울 `asia-northeast3` 등)에 자유롭게 배포 가능합니다.

```bash
# [Case A: Aiven 또는 외부 PostgreSQL 사용 시 (추천 - 100% 무료)]
# 1) 시크릿 등록
just setup-secrets -b "postgresql+asyncpg://avnadmin:<PASSWORD>@<HOST>:<PORT>/defaultdb?ssl=require"

# 2) Cloud Run 배포 (Cloud SQL 옵션 없이 바로 실행)
just deploy-cloud-run

# [Case B: Google Cloud SQL 사용 시]
# 1) 시크릿 등록
just setup-secrets -c "PROJECT:REGION:INSTANCE"

# 2) Cloud Run 배포
just deploy-cloud-run -c "PROJECT:REGION:INSTANCE"
```
*(개별 세부 단계를 수동으로 실행하려면 아래의 1~6단계를 참고하세요.)*

---


## 1. 사전 준비 (GCP 환경 설정)

### 1.1 GCP 프로젝트 및 변수 설정
```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="asia-northeast3" # 서울 리전 (또는 us-central1 등)
export SERVICE_NAME="auto-hub"
export REPO_NAME="auto-hub"
export DB_INSTANCE_NAME="auto-hub-db"

gcloud config set project "$PROJECT_ID"
```

### 1.2 필수 API 활성화
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

## 2. 데이터베이스 (Cloud SQL for PostgreSQL)

### 2.1 Cloud SQL 인스턴스 생성 (신규 생성 시)
> [!NOTE]
> 이미 사용 중인 PostgreSQL 인스턴스가 있다면 이 단계를 건너뛰고 2.2의 데이터베이스 및 사용자 생성만 진행하세요.

```bash
gcloud sql instances create "$DB_INSTANCE_NAME" \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region="$REGION" \
  --root-password="<STRONG_ROOT_PASSWORD>"
```

### 2.2 DB 및 사용자 생성
```bash
# 데이터베이스 생성
gcloud sql databases create auto_hub --instance="$DB_INSTANCE_NAME"

# 애플리케이션 사용자 생성
gcloud sql users create hub_user \
  --instance="$DB_INSTANCE_NAME" \
  --password="<STRONG_USER_PASSWORD>"
```

---

## 3. Secret Manager 시크릿 설정

민감한 설정 값은 Secret Manager에 등록하여 Cloud Run에 안전하게 주입합니다.

### 3.1 커넥터 토큰 암호화 마스터 키 (32바이트 AES 키)
```bash
openssl rand -base64 32 | gcloud secrets create connector-credential-key \
  --replication-policy=automatic \
  --data-file=-
```

### 3.2 관리 API 인증 키 (`APP_SECRET_KEY`)
Hub UI 및 관리 API 접속 시 사용할 키입니다:
```bash
openssl rand -hex 32 | gcloud secrets create auto-hub-app-secret \
  --replication-policy=automatic \
  --data-file=-
```
*(UI 최초 접속 시 이 키를 복사하여 입력합니다.)*

### 3.3 GitHub Webhook Secret (`GITHUB_WEBHOOK_SECRET`)
GitHub Webhook HMAC 서명 검증에 사용할 임의의 문자열:
```bash
openssl rand -hex 20 | gcloud secrets create auto-hub-webhook-secret \
  --replication-policy=automatic \
  --data-file=-
```

### 3.4 데이터베이스 접속 URL (`DATABASE_URL`)
Cloud Run은 Cloud SQL Unix Domain Socket(`/cloudsql/PROJECT:REGION:INSTANCE`)을 통해 연결합니다:
```bash
# Cloud SQL Connection Name 확인
export DB_CONNECTION_NAME=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --format="value(connectionName)")

# DATABASE_URL 시크릿 생성
# 형식: postgresql+asyncpg://<USER>:<PASSWORD>@/<DB_NAME>?host=/cloudsql/<CONNECTION_NAME>
echo -n "postgresql+asyncpg://hub_user:<STRONG_USER_PASSWORD>@/auto_hub?host=/cloudsql/${DB_CONNECTION_NAME}" | \
  gcloud secrets create auto-hub-database-url \
  --replication-policy=automatic \
  --data-file=-
```

---

## 4. 서비스 계정(IAM) 권한 부여

Cloud Run 기본 컴퓨팅 서비스 계정(또는 전용 서비스 계정)에 Cloud SQL 및 Secret Manager 접근 권한을 부여합니다.

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

## 5. 컨테이너 빌드 & Cloud Run 배포

로컬에 Docker 데몬이 없어도 **Google Cloud Build**를 통해 클라우드에서 바로 빌드할 수 있습니다.

### 5.1 Artifact Registry 저장소 생성
```bash
gcloud artifacts repositories create "$REPO_NAME" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Auto Hub docker repository"
```

### 5.2 Cloud Build로 빌드 및 푸시
프로젝트 루트 디렉토리(`/home/mj/projects/auto-hub`)에서 실행합니다:
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

### 5.3 Cloud Run 서비스 배포
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
  --set-env-vars="CONNECTOR_CREDENTIAL_KEY_SECRET=projects/${PROJECT_ID}/secrets/connector-credential-key,CONNECTOR_CREDENTIAL_KEY_VERSION=1" \
  --set-secrets="APP_SECRET_KEY=auto-hub-app-secret:latest,DATABASE_URL=auto-hub-database-url:latest,GITHUB_WEBHOOK_SECRET=auto-hub-webhook-secret:latest"
```

배포 완료 시 출력되는 Service URL(예: `https://auto-hub-xxxx-du.a.run.app`)을 기록합니다:
```bash
export SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)")
echo "Auto Hub Service URL: $SERVICE_URL"
```

---

## 6. Cloud Scheduler 등록 (주기적 트리거)

Auto Hub의 감시/재시도 스케줄러 틱을 실행하기 위해 Cloud Scheduler를 등록합니다.

```bash
gcloud scheduler jobs create http auto-hub-dispatcher-tick \
  --location="$REGION" \
  --schedule="* * * * *" \
  --uri="${SERVICE_URL}/api/v1/dispatchers/trigger" \
  --http-method=POST \
  --headers="X-API-Key=$(gcloud secrets versions access latest --secret=auto-hub-app-secret)" \
  --time-zone="UTC" \
  --attempt-deadline=300s
```

---

## 7. 배포 후 확인 및 연동 (Implementation Plan 실전 검증)

1. **웹 브라우저 접속 확인**
   - `${SERVICE_URL}/` 로 접속하여 Hub UI 대시보드 화면이 로드되는지 확인합니다.
   - 우측 상단 또는 로그인 모달에서 `auto-hub-app-secret` 키 값을 입력하여 로그인합니다.
2. **Swagger Docs 확인**
   - `${SERVICE_URL}/docs` 에서 API 문서가 정상 응답하는지 확인합니다.
3. **GitHub 저장소 Webhook 등록 (Phase 5 연동)**
   - 대상 GitHub 저장소의 `Settings → Webhooks → Add webhook` 이동
   - **Payload URL**: `${SERVICE_URL}/api/v1/webhooks/github`
   - **Content type**: `application/json`
   - **Secret**: `auto-hub-webhook-secret` 값 입력
   - **Events**: `Let me select individual events` 선택 후:
     - `Pull requests`
     - `Issue comments`
     - `Workflow runs`
   - 등록 후 GitHub의 `Recent Deliveries`에서 Ping(200 OK) 전달 확인.
4. **Phase 3.4 Canary 테스트 진행**
   - UI에서 프로젝트 등록 및 PR 등록(Enroll PR)을 실행하여 `@codex` 멘션 및 `awaiting_ci` 전이 확인.
