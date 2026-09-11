from datetime import UTC, datetime
from uuid import UUID

import pytest
from app.features.pipeline_runs.dispatch import build_codex_for_linear_comment
from app.features.pipeline_runs.schemas import ImplementationRequest
from app.features.projects.schemas import LinearIssue

pytestmark = pytest.mark.unit


def test_codex_for_linear_comment_pins_repository_and_carries_marker():
    request = ImplementationRequest(
        correlation_marker="hub-attempt:00000000-0000-0000-0000-000000000001",
        repository="owner/repository",
        base_branch="main",
        head_branch="codex/hub-1",
        issue=LinearIssue(
            id=UUID(int=1),
            identifier="HUB-1",
            title="Add health response",
            description="Sensitive implementation context stays on the issue",
            priority=2,
            state_type="started",
            created_at=datetime(2026, 9, 11, tzinfo=UTC),
            updated_at=datetime(2026, 9, 11, tzinfo=UTC),
            url="https://linear.app/example/issue/HUB-1",
        ),
        instructions="Implement the issue",
    )

    comment = build_codex_for_linear_comment(request)

    assert comment == "\n".join(
        (
            "@Codex implement this issue in owner/repository.",
            "Use `main` as the base and `codex/hub-1` as the working branch.",
            "Follow the repository instructions and run its required checks.",
            "Correlation: `hub-attempt:00000000-0000-0000-0000-000000000001`",
        )
    )
    assert request.issue.description is not None
    assert request.issue.description not in comment
