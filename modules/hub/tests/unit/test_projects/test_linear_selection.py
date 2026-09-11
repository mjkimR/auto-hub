from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.features.projects.linear import select_actionable_issue
from app.features.projects.schemas import LinearIssue, LinearIssueBlocker

pytestmark = pytest.mark.unit
NOW = datetime(2026, 9, 11, tzinfo=UTC)


def make_issue(
    number: int,
    *,
    priority: int = 3,
    state_type: str = "unstarted",
    created_offset: int = 0,
    blocker_states: tuple[str, ...] = (),
) -> LinearIssue:
    return LinearIssue(
        id=UUID(int=number),
        identifier=f"HUB-{number}",
        title=f"Issue {number}",
        priority=priority,
        state_type=state_type,
        created_at=NOW + timedelta(minutes=created_offset),
        updated_at=NOW,
        url=f"https://linear.app/example/issue/HUB-{number}",
        blockers=[
            LinearIssueBlocker(id=UUID(int=100 + index), identifier=f"HUB-{100 + index}", state_type=state)
            for index, state in enumerate(blocker_states)
        ],
    )


class TestSelectActionableIssue:
    def test_urgent_issue_wins_and_no_priority_sorts_last(self):
        result = select_actionable_issue(
            [make_issue(1, priority=0), make_issue(2, priority=2), make_issue(3, priority=1)]
        )
        assert result.selected and result.selected.identifier == "HUB-3"
        assert result.actionable_count == 3

    def test_equal_priority_uses_creation_time_then_issue_id(self):
        result = select_actionable_issue(
            [
                make_issue(3, created_offset=1),
                make_issue(2, created_offset=0),
                make_issue(1, created_offset=0),
            ]
        )
        assert result.selected and result.selected.identifier == "HUB-1"

    def test_unresolved_blocker_excludes_issue(self):
        result = select_actionable_issue(
            [make_issue(1, priority=1, blocker_states=("started",)), make_issue(2, priority=4)]
        )
        assert result.selected and result.selected.identifier == "HUB-2"
        assert result.blocked_count == 1

    def test_selection_uses_state_types_instead_of_workspace_state_names(self):
        result = select_actionable_issue(
            [
                make_issue(1, priority=1, state_type="custom_ready", blocker_states=("custom_in_progress",)),
                make_issue(2, priority=2, state_type="custom_backlog"),
            ]
        )
        assert result.selected and result.selected.identifier == "HUB-2"

    @pytest.mark.parametrize("blocker_state", ["completed", "canceled"])
    def test_terminal_blocker_is_resolved(self, blocker_state):
        result = select_actionable_issue([make_issue(1, blocker_states=(blocker_state,))])
        assert result.selected and result.selected.identifier == "HUB-1"

    @pytest.mark.parametrize("state_type", ["completed", "canceled"])
    def test_terminal_issue_is_never_selected(self, state_type):
        result = select_actionable_issue([make_issue(1, state_type=state_type)])
        assert result.selected is None
        assert result.inspected_count == 1
        assert result.actionable_count == 0
        assert result.blocked_count == 0
