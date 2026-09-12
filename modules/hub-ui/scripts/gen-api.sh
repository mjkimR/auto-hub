#!/usr/bin/env sh
# Extract the OpenAPI schema from the FastAPI app and generate TypeScript types (schema.d.ts).
# Usage: sh scripts/gen-api.sh
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
hub_dir="$repo/modules/hub"

api_dir="$here/../src/lib/api"
mkdir -p "$api_dir"
schema_json="$api_dir/openapi.json"
schema_ts="$api_dir/schema.d.ts"

echo "Exporting OpenAPI JSON from Auto-Hub FastAPI backend..."
PYTHONPATH="$hub_dir" uv run --directory "$hub_dir" python -c \
  "import json; from app.main import create_app; print(json.dumps(create_app().openapi(), indent=2))" \
  > "$schema_json"

echo "Generating TypeScript definitions with openapi-typescript..."
npx openapi-typescript "$schema_json" -o "$schema_ts"

cd "$here/.."
rm -f "$schema_json"
echo "Formatting generated schema..."
npm run format "$schema_ts"

echo "Generated: $schema_ts"
