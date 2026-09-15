# Development & Operations

## Commands

Refer to the [justfile](../justfile) for actual targets, aliases, defaults, and implementations.

```sh
just init
just dev-run hub
just dev-run hub-ui
just lint
just check
just test
just test-ui
just gen-ui-api
```

`just lint` automatically fixes Python formatting and lints.
`just check` runs Python type checking and the Frontend production build.
Default tests use SQLite; `just test-pg` uses PostgreSQL testcontainers and needs a running Docker daemon.
`just test-ui` runs the frontend component test suite.
When API definitions change, run `just gen-ui-api` to regenerate the client SDK.
Frontend commands activate the Node version in `.nvmrc` through nvm; if that version is not installed, `nvm use` fails and `just gen-ui-api` exits with status 3 without further output.
The Frontend strictly consumes the generated SDK.

## Existing Scheduler Foundation

The backend follows the `API → UseCase → Service → Repository` clean architecture flow.
Tasks are registered with `@task(name="namespace.name")` and Pydantic payloads.
Domain packages must be imported in `app/features/execution/tasks/domains/__init__.py` for auto-discovery.
Task schemas can be inspected via `/api/v1/tasks/specs`.

`ScheduleConfig` stores cron or interval configuration alongside the payload.
The dispatcher claims due schedules inside a database transaction and records a `ScheduleJob`.
While PostgreSQL's `FOR UPDATE SKIP LOCKED` coordinates concurrent schedule selection, it does not solve external request deduplication, unexpected process termination, or tick overlaps on its own.

`ScheduleJob` records pending/success/failure states and timestamps.
Failure messages report the request ID; detailed exceptions remain in server logs.
Never log credentials or personally identifiable information (PII).
Even if the pipeline CI fails, if the observation query itself succeeds, the `ScheduleJob` is marked as success.
CI status and failure rationales are inspected via the observation report.

## Database & Credentials

The production database is PostgreSQL, and migrations are managed with Alembic.
Refer to the `justfile` for `just db-upgrade` and `just db-revision` arguments.
GitHub credentials are stored encrypted in Connectors.
For encryption key configuration, follow the [Hub module documentation](../modules/hub/README.md#connector-credential-encryption).
API authentication relies on the existing API key mechanism.

## Runtime Environment

The baseline deployment model hosts the backend on Cloud Run, with Cloud Scheduler triggering `POST /api/v1/dispatchers/trigger`. This does not imply full deployment automation is complete.
Currently, HTTP trigger responses return after tasks for that tick finish executing.
Align timeouts across the application, Cloud Run, and Cloud Scheduler; pipeline observation tasks must complete inspection and persistence within their own bounded timeout and exit cleanly.

## Testing

External GitHub calls are isolated by swapping the HTTP transport, while DB persistence is verified against real test databases.
Complex pure CI evaluation logic is verified through unit tests, while API/schedule/report integration is verified through integration and E2E tests.
For fixtures and conventions, consult the [Testing Guide](../.agents/skills/hub-testing-expert/references/TESTING_GUIDE.md).
