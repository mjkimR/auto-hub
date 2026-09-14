# AGENTS.md - Guide for AI Assistants

This repository is a full-stack **Scheduler Manager** (cron/interval orchestrator) for Google Cloud Platform.
- **Backend**: `modules/hub` (Python, FastAPI, Clean Architecture)
- **Frontend**: `modules/hub-ui` (Svelte 5 Runes, SvelteKit 2 SPA, Vite 8, Tailwind CSS v4, shadcn-svelte, openapi-fetch)

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
- **Launch Development Servers**: `just dev-run` (Launches backend & frontend) | `just dev-run hub-ui` (Frontend only)
- **Linting & Code Formatting**: `just lint` (Lints all) | `just lint hub-ui` (Frontend only)
- **Type Checking & Compilation**: `just check` (Checks all) | `just check hub-ui` (Frontend only)
- **Generate API Client**: `just gen-ui-api` (Syncs backend OpenAPI schema with frontend openapi-typescript SDK)
- **Database Migrations**: `just db-upgrade` | `just db-revision "<message>"`

---

## Architecture & Code Style

### Backend (`modules/hub`)
- **Flow**: `API (Router) -> UseCase -> Service -> Repository` (Clean Architecture).
- **DI**: Use FastAPI's `Depends` and `Annotated`.
- **Tasks**: Decorate with `@task(name="namespace.name")` in `app/features/execution/tasks`. Always use Pydantic models for payloads.

### Frontend (`modules/hub-ui`)
- **Tech Stack**: Svelte 5 (Runes forced mode), SvelteKit 2 (SPA), TypeScript, Tailwind CSS v4, shadcn-svelte (bits-ui), openapi-fetch, zod.
- **Styling**: Tailwind CSS v4 CSS-first design system in `src/routes/layout.css`, OKLCH tokens, dark/light theme with `mode-watcher`.
- **Client Integration**: Import typed client resources from `$lib/api` (`api` client generated via `just gen-ui-api`).

---

## Critical Constraints

1. **Security**: NEVER commit `.env` files. NEVER log PII.
2. **Commits**: Concise, imperative, and **no emojis** (e.g., "Add user-defined timeout").
3. **Pre-flight Checks**: Always run `just lint` and verification builds before proposing a final solution.
4. **Git Commit**: Do not execute `git commit` commands or perform commits automatically unless explicitly requested or approved by the user.


