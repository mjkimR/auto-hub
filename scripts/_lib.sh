#!/usr/bin/env bash
# scripts/_lib.sh — Shared helpers for module resolution
# Source this file from other scripts: source "$(dirname "$0")/_lib.sh"
# Or from justfile recipes: source ./scripts/_lib.sh

AVAILABLE_MODULES="all hub hub-ui"

resolve_module() {
    case "$1" in
        hub|back|backend) echo "hub" ;;
        hub-ui|ui|front|frontend|svelte|hub-ui-svelte) echo "hub-ui" ;;
        all) echo "all" ;;
        *) echo "$1" ;;
    esac
}

resolve_module_path() {
    case "$1" in
        hub) echo "modules/hub" ;;
        hub-ui) echo "modules/hub-ui" ;;
        *) echo "modules/$1" ;;
    esac
}

should_run() { [ "$1" = "all" ] || [ "$1" = "$2" ]; }

# `just` recipes run in non-interactive shells, so they do not load ~/.bashrc
# and therefore do not inherit nvm's selected Node version.  When nvm is
# available, honor this repository's .nvmrc before running frontend tooling.
activate_frontend_node() {
    local nvm_dir="${NVM_DIR:-$HOME/.nvm}"
    local node_version_file="$(pwd)/.nvmrc"

    if [ -s "$nvm_dir/nvm.sh" ]; then
        export NVM_DIR="$nvm_dir"
        # shellcheck disable=SC1090
        . "$NVM_DIR/nvm.sh"
        nvm use --silent
    elif [ -f "$node_version_file" ]; then
        echo "nvm is unavailable; using $(command -v node || echo 'no node') instead of Node $(tr -d '[:space:]' < "$node_version_file")" >&2
    fi
}
