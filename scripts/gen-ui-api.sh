#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

hub_path=$(resolve_module_path "hub")
ui_path=$(resolve_module_path "hub-ui")

echo "Exporting OpenAPI JSON from Python backend..."
PYTHONPATH="$hub_path" uv run --directory "$hub_path" python -c \
  "import json; from app.main import create_app; print(json.dumps(create_app().openapi()))" \
  > "$ui_path/openapi.json"

echo "Generating API client..."
npm --prefix "$ui_path" run gen:api

rm -f "$ui_path/openapi.json"
echo "Frontend API client successfully generated!"
