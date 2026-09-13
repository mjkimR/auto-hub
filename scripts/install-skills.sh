#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_COMMON_LOCAL="$(cd "$REPO_ROOT/../app-common" 2>/dev/null && pwd || echo "")"

# In a multi-module repository, inspect workspace manifests (modules/hub/pyproject.toml or uv.lock)
if [ "$#" -eq 0 ]; then
    skills=()
    for manifest in "$REPO_ROOT/modules/hub/pyproject.toml" "$REPO_ROOT/uv.lock"; do
        if [ -f "$manifest" ]; then
            grep -qE "app-layer-base|app-tools|app-error" "$manifest" 2>/dev/null && skills+=(app-backend-core)
            if grep -q "app-tools" "$manifest" 2>/dev/null; then
                skills+=(app-local-dev app-package-update)
            fi
            grep -q "app-testing-base" "$manifest" 2>/dev/null && skills+=(app-testing)
            grep -q "app-file-storage" "$manifest" 2>/dev/null && skills+=(app-file-storage)
            grep -q "app-vector-store" "$manifest" 2>/dev/null && skills+=(app-vector-store)
            grep -q "app-http-client" "$manifest" 2>/dev/null && skills+=(app-http-client)
            grep -q "app-ai-catalog" "$manifest" 2>/dev/null && skills+=(app-ai-catalog)
            grep -q "app-mcp" "$manifest" 2>/dev/null && skills+=(app-mcp)
            grep -q "app-prebuilt-user" "$manifest" 2>/dev/null && skills+=(app-prebuilt-user)
            grep -q "app-prebuilt-outbox" "$manifest" 2>/dev/null && skills+=(app-prebuilt-outbox)
            if [ -d "$REPO_ROOT/modules/hub-ui" ] || [ -f "$REPO_ROOT/package.json" ]; then
                skills+=(app-svelte-ui)
            fi
            break
        fi
    done
    set -- "${skills[@]}"
fi

if [ -n "$APP_COMMON_LOCAL" ] && [ -f "$APP_COMMON_LOCAL/agents/link-skills.sh" ]; then
    echo "Linking skills from local app-common ($APP_COMMON_LOCAL)..."
    bash "$APP_COMMON_LOCAL/agents/link-skills.sh" "$@"
else
    echo "Installing skills remotely from app-common repository..."
    curl -sSL https://raw.githubusercontent.com/mjkimR/app-common/main/scripts/install-skills.sh | bash -s -- "$@"
fi
