available_modules := "hub"
default_test_path := "modules/hub"
default_pytest_options := "-q --tb=short --disable-warnings --no-header"
default_pytest_progress_line_filter := "^[\\.sFxFw]*\\s+\\[.*\\]$"

# Print available commands
default:
    @just --list

# Initialize the project (sync dependencies, install hooks, etc)
init:
    uv sync
    just hooks-install

# Run ruff format and lint
lint:
    uv run ruff format
    uv run ruff check --fix

# Run pyright static type checking
check:
    uv run pyright

# Install pre-commit hooks
hooks-install:
    uv run pre-commit install

# Run pre-commit hooks against all files
hooks-run:
    uv run pre-commit run --all-files

# Run backend server for a specific module in development mode
dev-run module:
    @AVAILABLE_MODULES="{{available_modules}}" bash ./scripts/dev-run.sh "{{module}}"

# Build docker image for a specific module or all modules
docker-build module="all" tag="latest":
    @AVAILABLE_MODULES="{{available_modules}}" bash ./scripts/docker-build.sh "{{module}}" "{{tag}}"

# Generate a new database migration for hub
db-revision message module="hub":
    cd modules/{{module}} && uv run alembic revision --autogenerate -m "{{message}}"

# Apply database migrations to head for hub
db-upgrade module="hub":
    cd modules/{{module}} && uv run alembic upgrade head

# Run tests with specified database type and paths
_run_tests db_type +paths:
    #!/usr/bin/env bash
    set -u
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' EXIT
    status=0
    uv run pytest {{default_pytest_options}} --db-type {{db_type}} {{paths}} >"$tmp" 2>&1 || status=$?
    grep -vE '{{default_pytest_progress_line_filter}}' "$tmp" || true
    exit "$status"

# Run tests with SQLite (default)
test +paths=default_test_path:
    @just _run_tests sqlite {{paths}}

# Run tests with PostgreSQL
test-pg +paths=default_test_path:
    @just _run_tests postgres {{paths}}

# Generate OpenAPI client for the frontend UI module
gen-ui-api:
    @echo "Exporting OpenAPI JSON from Python backend..."
    cd modules/hub && PYTHONPATH=. uv run python -c "import json; from app.main import create_app; print(json.dumps(create_app().openapi()))" > ../hub-ui/openapi.json
    @echo "Generating API client..."
    cd modules/hub-ui && npm run gen:api
    @rm -f modules/hub-ui/openapi.json
    @echo "Frontend API client successfully generated!"