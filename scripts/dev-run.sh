#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

target=$(resolve_module "${1:?Usage: dev-run.sh <module>}")

PID_UI=""
PID_HUB=""
PID_UI_SVELTE=""

if [ "$target" = "hub-ui-svelte" ]; then
    path=$(resolve_module_path "hub-ui-svelte")
    echo "Starting Svelte frontend ($path)..."
    npm --prefix "$path" run dev &
    PID_UI_SVELTE=$!
fi

if should_run "$target" "hub-ui"; then
    path=$(resolve_module_path "hub-ui")
    echo "Starting React frontend ($path)..."
    npm --prefix "$path" run dev &
    PID_UI=$!
fi

if should_run "$target" "hub"; then
    path=$(resolve_module_path "hub")
    echo "Starting Python backend ($path)..."
    if [ -f "$path/.env" ]; then
        set -a
        source "$path/.env"
        set +a
    fi
    just db-upgrade
    uv run --directory "$path" uvicorn app.main:create_app --port 8389 --reload &
    PID_HUB=$!
fi

# Set up clean up for processes on script termination
cleanup() {
    echo "Stopping development servers..."
    [ -n "$PID_UI" ] && kill "$PID_UI" 2>/dev/null || true
    [ -n "$PID_UI_SVELTE" ] && kill "$PID_UI_SVELTE" 2>/dev/null || true
    [ -n "$PID_HUB" ] && kill "$PID_HUB" 2>/dev/null || true
}

PIDS=()
[ -n "$PID_UI" ] && PIDS+=("$PID_UI")
[ -n "$PID_UI_SVELTE" ] && PIDS+=("$PID_UI_SVELTE")
[ -n "$PID_HUB" ] && PIDS+=("$PID_HUB")

if [ ${#PIDS[@]} -ne 0 ]; then
    trap cleanup SIGINT SIGTERM EXIT
    wait -n "${PIDS[@]}"
    echo "One of the background components stopped. Shutting down remaining servers..."
fi

