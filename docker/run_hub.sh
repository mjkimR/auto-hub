#!/bin/bash
set -ex

# 1) Run DB migrations
alembic upgrade head

# 2) Start FastAPI server
exec uvicorn "app.main:create_app" --factory --host 0.0.0.0 --port "$PORT" --workers "${WORKERS:-3}" --timeout-keep-alive "${TIMEOUT:-1200}" --proxy-headers --forwarded-allow-ips "*"

