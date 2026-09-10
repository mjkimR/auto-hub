# Auto Hub

Auto Hub is a personal development automation hub connecting GitHub, Linear, and Codex.
Building on top of the existing Scheduler Manager foundation (schedules, execution history, and connector management),
it incrementally constructs capabilities to manage work progress across multiple repositories.

## Direction

- A single connection maps **1 GitHub repository ↔ 1 Linear project**.
- **Hub** handles task selection, progress tracking, revision requests, retries, pause/resume, and merge policies.
- **GitHub Actions in the target repository** handles environment setup, testing, linting, and building.
- Existing CIs can be connected as-is, while repositories without CI are provided with [templates](templates/github-actions/README.md).
- Differences between repositories are expressed through required verification, review/merge policies, and the repository's own tests.

The target workflow is: `Linear issue → Codex implementation → PR verification → Revision or merge → Linear completion`.
Drawing on operational experience from `g-sandbox`, Godot-specific logic, planning notes, and multi-prototype rules are kept out of the core engine.

## Implementation Status

The existing scheduler and management UI are preserved. The current implementation scope is **read-only CI observation on saved project connections**.
A repository and a Linear project are registered as one connection, a connection check confirms CI is readable and verifies one current PR, and scheduled runs persist the latest observation of the required GitHub Actions jobs.
The CI templates serve as starter files to install in target repositories, and existing `pipeline.observe` schedules can be imported onto a project connection.

Linear issue selection, Codex dispatch, manual CI execution, automated revision/merge, long-term execution history (`PipelineRun`), and distribution of shared reusable workflows are planned as follow-up work.
Currently, a status of `passed` in observation results signifies fulfillment of the CI contract, not approval for merge.

## Documentation

| Document | Content |
| --- | --- |
| [Documentation Guide](docs/README.md) | Reading order and document roles |
| [Architecture](docs/architecture.md) | Responsibilities and state ownership across Hub, repositories, and external services |
| [CI Connection Contract](docs/ci-contract.md) | Required verification, result evaluation, connection and execution examples |
| [Implementation Plan](docs/implementation-plan.md) | Initial implementation scope and follow-up milestones |
| [Development & Operations](docs/development.md) | Existing scheduler foundation and local verification |
| [CI Templates](templates/github-actions/README.md) | Initial setup for Python+uv and Node+npm |

## Development

The backend is built with Python/FastAPI in `modules/hub`, and the frontend is built with React/TypeScript in `modules/hub-ui`.
PostgreSQL is the standard database, with SQLite used for default testing.

The single source of truth for execution commands and default arguments is [justfile](justfile). Check available commands with `just --list`.

```sh
just init
just dev-run hub
just dev-run hub-ui
just lint
just check
just test
```

For connector credential encryption setup, refer to the [Hub module documentation](modules/hub/README.md#connector-credential-encryption).
