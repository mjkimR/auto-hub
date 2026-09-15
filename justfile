default_test_path := "modules/hub"

# Print available commands
default:
    @just --list

# Initialize project modules (all, hub, or hub-ui)
init module="all":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")

    if should_run "$target" "hub"; then
        path=$(resolve_module_path "hub")
        echo "Initializing Python backend ($path)..."
        uv sync
        just hooks-install
        just link-skills
    fi

    if should_run "$target" "hub-ui"; then
        path=$(resolve_module_path "hub-ui")
        echo "Initializing Svelte frontend ($path)..."
        activate_frontend_node
        npm --prefix "$path" install
    fi

# Run linters for a specific module (all, hub, or hub-ui)
lint module="all":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")

    if should_run "$target" "hub"; then
        path=$(resolve_module_path "hub")
        echo "Linting Python backend ($path)..."
        uv run --directory "$path" ruff format
        uv run --directory "$path" ruff check --fix
    fi

    if should_run "$target" "hub-ui"; then
        path=$(resolve_module_path "hub-ui")
        echo "Linting Svelte frontend ($path)..."
        activate_frontend_node
        npm --prefix "$path" run lint
    fi

# Run static type checks for a specific module (all, hub, or hub-ui)
check module="all":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")

    if should_run "$target" "hub"; then
        path=$(resolve_module_path "hub")
        echo "Type checking Python backend ($path)..."
        uv run --directory "$path" pyright
    fi

    if should_run "$target" "hub-ui"; then
        path=$(resolve_module_path "hub-ui")
        echo "Checking and compiling Svelte frontend ($path)..."
        activate_frontend_node
        npm --prefix "$path" run check
        npm --prefix "$path" run build
    fi

# Install pre-commit hooks
hooks-install:
    uv run pre-commit install

# Run pre-commit hooks against all files
hooks-run:
    uv run pre-commit run --all-files

# Run server for a specific module in development mode (hub or hub-ui)
dev-run module="all":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    bash ./scripts/dev-run.sh "$target"

# Kill any dangling development servers (FastAPI on 8389, Vite on 5173)
kill:
    #!/usr/bin/env bash
    echo "Terminating dangling development processes..."
    # Release ports 8389 (backend) and 5173 (frontend)
    fuser -k 8389/tcp 2>/dev/null || true
    fuser -k 5173/tcp 2>/dev/null || true
    # Fallback to process name-based termination (disabled to prevent race conditions and accidental termination of unrelated servers)
    # pkill -f "uvicorn.*app.main:create_app" 2>/dev/null || true
    # pkill -f "vite" 2>/dev/null || true
    echo "Development servers cleaned up."

# Compile frontend production bundle
build-ui:
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    path=$(resolve_module_path "hub-ui")
    activate_frontend_node
    npm --prefix "$path" run build

# Build docker image for a specific module or all modules
docker-build module="all" tag="latest":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    bash ./scripts/docker-build.sh "$target" "{{ tag }}"

# Generate a new database migration for hub
db-revision message module="hub":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    path=$(resolve_module_path "$target")
    uv run --directory "$path" alembic revision --autogenerate -m "{{ message }}"

# Apply database migrations to head for hub
db-upgrade module="hub":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    path=$(resolve_module_path "$target")
    if [ -f "$path/.env" ]; then
        set -a
        source "$path/.env"
        set +a
    fi
    uv run --directory "$path" alembic upgrade head

# Run tests with SQLite (default)
test +paths=default_test_path:
    @bash ./scripts/run-tests.sh sqlite {{ paths }}

# Run tests with PostgreSQL
test-pg +paths=default_test_path:
    @bash ./scripts/run-tests.sh postgres {{ paths }}

# Run frontend tests
test-ui:
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    path=$(resolve_module_path "hub-ui")
    activate_frontend_node
    npm --prefix "$path" test

# Generate OpenAPI client for the frontend UI module from Python backend schema
gen-ui-api:
    @bash ./scripts/gen-ui-api.sh

# Sync the local signed-in Codex quota reset time to the global personal-codex AI catalog.
sync-codex-quota:
    @uv run python ./scripts/sync-codex-quota.py

# Link or install agent skills from app-common
link-skills +args="":
    @bash ./scripts/install-skills.sh {{ args }}

# Setup Secret Manager secrets for Cloud Run
setup-secrets +args="":
    @bash ./docker/helper/setup_secrets.sh {{ args }}

# Deploy Auto Hub to Cloud Run via Cloud Build
deploy-cloud-run +args="":
    @bash ./docker/helper/deploy_cloud_run.sh {{ args }}

# Register or update GitHub Webhook for a repository via gh CLI
register-webhook repo:
    @bash ./scripts/register-webhook.sh {{ repo }}

# Update API key across Secret Manager, Cloud Scheduler, Cloud Run, and local .env
update-api-key key="":
    @bash ./scripts/update-api-key.sh {{ key }}

