# AGENTS.md - Guide for AI Assistants

This repository is a full-stack **Scheduler Manager** (cron/interval orchestrator) for Google Cloud Platform.
- **Backend**: `modules/hub` (Python, FastAPI, Clean Architecture)
- **Frontend**: `modules/hub-ui` (React 19, Vite, Ant Design v6, React Query v5, Zustand)

---

## Tooling & Commands

We use **just** as the primary command runner and task orchestrator.

> [!IMPORTANT]
> **The `justfile` is the Single Source of Truth (SSOT).**
> Do NOT rely on hardcoded arguments in documentation. Always read the `justfile` directly to inspect available targets, aliases (e.g., `back`/`front`), parameter defaults, and task implementation scripts.

### Scripts & Shared Infrastructure
- **Separation of Concerns**: Avoid writing complex bash commands inline in `justfile` recipes. Delegate execution logic to dedicated shell scripts inside the `scripts/` directory to keep the `justfile` as a thin orchestration layer.

### Quick Command Reference Examples
- **Initialize Modules**: `just init` (Initializes all) | `just init hub` (Backend only) | `just init hub-ui` (Frontend only)
- **Launch Development Servers**: `just dev-run` (Launches backend) | `just dev-run hub-ui` (Launches frontend dev-server)
- **Linting & Code Formatting**: `just lint` (Lints all) | `just lint hub-ui` (Frontend only)
- **Type Checking & Compilation**: `just check` (Checks all) | `just check hub-ui` (Frontend only)
- **Generate API Client**: `just gen-ui-api` (Syncs backend OpenAPI schemas with frontend React Query SDK)
- **Database Migrations**: `just db-upgrade` | `just db-revision "<message>"`

---

## Architecture & Code Style

### Backend (`modules/hub`)
- **Flow**: `API (Router) -> UseCase -> Service -> Repository` (Clean Architecture).
- **DI**: Use FastAPI's `Depends` and `Annotated`.
- **Tasks**: Decorate with `@task(name="namespace.name")` in `app/features/tasks`. Always use Pydantic models for payloads.

### Frontend (`modules/hub-ui`)
- **Tech Stack**: React 19, TypeScript, Ant Design v6, React Query v5, Zustand.
- **Styling**: Vanilla CSS variable overrides for tailored HSL light/dark themes and glassmorphic designs.
- **Client Integration**: Never use `fetch` directly. Always import client resources from `src/generated/api/sdk.gen.ts`.

---

## Critical Constraints

1. **Security**: NEVER commit `.env` files. NEVER log PII.
2. **Commits**: Concise, imperative, and **no emojis** (e.g., "Add user-defined timeout").
3. **Pre-flight Checks**: Always run `just lint` and verification builds before proposing a final solution.



