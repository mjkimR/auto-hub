# Documentation Guide

Auto Hub is expanding the existing Scheduler Manager into a development automation service.
These documents explicitly distinguish between design goals and current functionality.

1. [Architecture](architecture.md): Responsibility boundaries and the scope of the core engine.
2. [CI Connection Contract](ci-contract.md): Configuration required when connecting a repository and current observation APIs.
3. [Codex PR Mention Protocol](codex-pr-mention.md): Design contract for dispatching Codex cloud work through PR comments.
4. [Delivery Status](delivery-status.md): Delivered capabilities, verification record, and optional follow-ups.
5. [Development & Operations](development.md): Commands, testing, and constraints of the existing scheduler foundation.

[CI Template Usage](../templates/github-actions/README.md) covers CI setup in target repositories.
The root `justfile` is the single source of truth for commands, and connector credential encryption details are documented in the [Hub module documentation](../modules/hub/README.md#connector-credential-encryption).

When introducing new implementations, update the delivery status alongside the corresponding feature documentation.
Never document APIs or commands as available features before they actually exist.
