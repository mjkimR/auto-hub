#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_COMMON_LOCAL="$(cd "$REPO_ROOT/../app-common" 2>/dev/null && pwd || echo "")"

if [ -n "$APP_COMMON_LOCAL" ] && [ -f "$APP_COMMON_LOCAL/agents/link-skills.sh" ]; then
    echo "Linking skills from local app-common ($APP_COMMON_LOCAL)..."
    bash "$APP_COMMON_LOCAL/agents/link-skills.sh" --auto "$@"
else
    echo "Installing skills remotely from app-common repository..."
    curl -sSL https://raw.githubusercontent.com/mjkimR/app-common/main/scripts/install-skills.sh | bash -s -- --auto "$@"
fi
