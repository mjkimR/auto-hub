#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

ui_path=$(resolve_module_path "hub-ui")

echo "Generating OpenAPI client for frontend UI module..."
activate_frontend_node
npm --prefix "$ui_path" run gen:api
echo "Frontend API client successfully generated!"
