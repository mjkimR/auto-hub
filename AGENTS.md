# AGENTS.md - Guide for AI Assistants

This repository is a Python-based **Scheduler Manager** that provides a lightweight hub for dispatching scheduled jobs (
cron/interval). It follows Clean Architecture principles and is designed for deployment on Google Cloud Platform.

## Tooling & Commands

We use **just** as a command runner.
Use the provided scripts to install it automatically:

- **macOS / Linux**: `./scripts/install-just.sh`
- **Windows**: `scripts\install-just.bat`

### Core Commands

- **Initialize Project**: `just init` (Syncs dependencies and installs git hooks)
- **Database Migrations**: `just db-upgrade` (Applies migrations to head for the hub module)
- **Generate Migration**: `just db-revision "<message>"`
- **Start Development Server**: `just dev-run hub` (Runs hub module in dev mode)
- **Lint & Format**: `just lint` (Runs ruff format and check)
- **Type Checking**: `pyright` (Run manually as needed)

## Testing Instructions

When writing or fixing tests, especially for the **hub** module, please refer to the specialized testing skill:

- **Skill**: `hub-testing-expert`
- **Guide**: [Detailed Testing Guide](.agents/skills/hub-testing-expert/references/TESTING_GUIDE.md)

This skill contains our Test Trophy model, shared fixtures, and standard patterns for E2E, Integration, and Unit tests.

### Quick Commands

- **Run All Tests**: `just test`

## Architecture & Code Style

- **Flow**: `API (Router) -> UseCase -> Service -> Repository`.
- **Structure**: Feature-based organization under `app/features/`.
- **DI**: Extensively use FastAPI's `Depends` and `Annotated`.
- **Tasks**:
    - Decorate with `@task(name="namespace.name")`.
    - Must reside in `app/features/tasks` (for autodiscovery).
    - Always use Pydantic models for payloads.

## CRITICAL CONSTRAINTS (DO NOT IGNORE)

1. **Security & Secrets**: **NEVER** commit `.env` files. **NEVER** log PII.
2. **Commit Formatting**:
    - Use concise, imperative messages (e.g., "Add user-defined timeout").
    - **NO EMOJIS** in commit messages or PR titles.
    - Keep changes surgical and strictly scoped to the prompt.
3. **Pre-flight Checks**: Always ensure tests and `just lint` would pass before proposing a final solution.

