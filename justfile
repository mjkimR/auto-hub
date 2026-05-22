available_modules := "hub"
default_test_path := "modules/hub"

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
db-revision message:
    cd modules/hub && uv run alembic revision --autogenerate -m "{{message}}"

# Apply database migrations to head for hub
db-upgrade:
    cd modules/hub && uv run alembic upgrade head

# Run tests with specified database type and paths
_run_tests db_type +paths:
    uv run pytest --db-type {{db_type}} {{paths}}

# Run tests with SQLite (default)
test +paths=default_test_path:
    @just _run_tests sqlite {{paths}}

# Run tests with PostgreSQL
test-pg +paths=default_test_path:
    @just _run_tests postgres {{paths}}