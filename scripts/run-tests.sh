#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

DB_TYPE=${1:?Usage: run-tests.sh <db_type> [paths...]}
shift
PATHS=("$@")

hub_path=$(resolve_module_path "hub")

# Normalize paths to be relative to modules/hub
UPDATED_PATHS=()
for path in "${PATHS[@]}"; do
    if [[ "$path" == modules/hub/* ]]; then
        UPDATED_PATHS+=("${path#modules/hub/}")
    elif [[ "$path" == "modules/hub" ]]; then
        UPDATED_PATHS+=(".")
    else
        UPDATED_PATHS+=("$path")
    fi
done

DEFAULT_PYTEST_OPTIONS="-q --tb=short --disable-warnings --no-header"
PYTEST_OPTIONS="${PYTEST_OPTIONS:-$DEFAULT_PYTEST_OPTIONS}"
PROGRESS_LINE_FILTER='^[\.sFxFw]*\s+\[.*\]$'

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
status=0
uv run --directory "$hub_path" pytest $PYTEST_OPTIONS --db-type "$DB_TYPE" "${UPDATED_PATHS[@]}" >"$tmp" 2>&1 || status=$?
grep -vE "$PROGRESS_LINE_FILTER" "$tmp" || true
exit "$status"
