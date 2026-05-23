#!/usr/bin/env bash
# scripts/_lib.sh — Shared helpers for module resolution
# Source this file from other scripts: source "$(dirname "$0")/_lib.sh"
# Or from justfile recipes: source ./scripts/_lib.sh

AVAILABLE_MODULES="all hub hub-ui"

resolve_module() {
    case "$1" in
        hub|back|backend) echo "hub" ;;
        hub-ui|ui|front|frontend) echo "hub-ui" ;;
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
