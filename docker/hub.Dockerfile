# ---- Frontend Builder Stage ----
FROM node:22-slim AS frontend-builder
WORKDIR /app/modules/hub-ui

COPY modules/hub-ui/package*.json ./
RUN npm ci

COPY modules/hub-ui ./
RUN npm run build

# ---- Backend Builder Stage ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS backend-builder
ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y \
    build-essential \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# uv workspace: root pyproject.toml + uv.lock, then member pyproject.toml
COPY pyproject.toml uv.lock ./
COPY modules/hub/pyproject.toml ./modules/hub/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --no-dev --package scheduler-mgr

# ---- Final Stage ----
FROM python:3.13-slim AS runtime
ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app/modules/hub
COPY --from=backend-builder /app/.venv /app/.venv
COPY --from=frontend-builder /app/modules/hub-ui/build ./ui_dist
COPY modules/hub/app ./app
COPY modules/hub/alembic.ini ./alembic.ini
COPY modules/hub/migrations ./migrations
COPY templates/github-actions /app/templates/github-actions
COPY docker/run_hub.sh ./run_hub.sh
RUN chmod +x run_hub.sh

ENV WORKERS=3
ENV TIMEOUT=1200

ENTRYPOINT ["./run_hub.sh"]

