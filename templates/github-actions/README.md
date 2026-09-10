# CI Starter Templates

Workflow files to install into target repositories. Files in this directory are not executed automatically by Auto Hub.
Currently provided for manual copying and adaptation; CLI generation and centralized reusable workflows are planned for subsequent phases.

| File | Prerequisites | Hub's required_jobs |
| --- | --- | --- |
| [python-uv.yml](python-uv.yml) | Python 3.13, uv.lock, dev dependencies include ruff and pytest | `lint`, `test` |
| [node-npm.yml](node-npm.yml) | Node 22, package-lock.json, lint/test/build scripts | `lint`, `test`, `build` |

## Installation

1. If CI already exists, do not install a new file; instead, register the existing workflow filename and exact required job names in Hub.
2. If CI is missing, copy a template to `.github/workflows/ci.yml` in the target repository.
3. Adjust runtime versions, dependency groups, and execution commands to match the project's command runner.
4. If databases, headless browsers, or game engines are required, add corresponding services and setup steps.
5. Open a PR in the target repository to verify that all required jobs execute successfully.
6. Register Hub's `verification.workflow` as `ci.yml` and `required_jobs` with the actual job names.

Templates assume a single package with a lockfile at the repository root. Workspace or subdirectory packages must adjust each job's working directory and cache dependency paths accordingly.
Auto Hub itself is a polyglot workspace mixing Python and Node, and does not use these starter templates directly.

The Python template does not enforce package builds. If distribution or package build verification is needed, add a `build` job.
For Node, `npm test` must be a command that terminates in CI; disable watch mode in the package scripts.
Missing test scripts fail explicitly rather than succeeding silently.

Verification commands must not modify files in-place. For example, Auto Hub's `just lint` performs in-place formatting and lint fixes, which must be kept distinct from read-only CI verification checks. Applying formatting and committing/pushing changes is the responsibility of implementation agents.

## Naming & Execution Rules

- The display name `name:` is the job name evaluated by Hub. Workflow names and filenames are distinct from job names.
- When using matrix strategies or reusable workflows, register the actual expanded job names as displayed in GitHub Actions.
- Do not use `continue-on-error` on required jobs.
- `skipped` or `neutral` outcomes for required jobs are not accepted as passed by Hub. If checks are conditionally omitted based on changed file paths, define an aggregation/gate job that explicitly validates sub-check conditions and designate that gate job as required.
- Starter templates run exclusively on `pull_request` events. Avoid duplicate triggers on both `push` and `pull_request`.
- New commits to the same PR cancel previous CI runs. Hub waits for the latest run matching the current head.
- Workflows must not mutate external issue statuses, mention Codex, or perform automatic merges.

Template versions are tracked via commits in this repository. Review and pin third-party Action references according to your team policy.
Repeated setup patterns will later be published as version-pinned reusable workflows.
