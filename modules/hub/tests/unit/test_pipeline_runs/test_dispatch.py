import json

import httpx
import pytest
from app.features.project_management.pipeline_runs.dispatch import build_codex_mention_comment, is_codex_quota_reply
from app.features.project_management.pipeline_runs.github import linked_issue_numbers
from app.features.project_management.pipeline_runs.schemas import (
    ImplementationRequest,
    LinkedIssue,
    PullRequestSnapshot,
)
from app.features.project_management.pipelines.github import GitHubActionsReader, GitHubObservationError

pytestmark = pytest.mark.unit

MARKER = "hub-attempt:00000000-0000-0000-0000-000000000001"
HEAD = "c" * 40


def make_request(**pull_overrides) -> ImplementationRequest:
    pull = {
        "number": 7,
        "url": "https://github.com/owner/repository/pull/7",
        "title": "Add health endpoint",
        "body": "Return 200 with a JSON status.",
        "base_ref": "main",
        "head_ref": "feature/health",
        "head_sha": HEAD,
        "linked_issues": [
            LinkedIssue(number=3, title="Health check", body="Load balancers need it.", url="https://example.test/3")
        ],
        **pull_overrides,
    }
    return ImplementationRequest(
        correlation_marker=MARKER,
        repository="owner/repository",
        pull_request=PullRequestSnapshot.model_validate(pull),
        instructions="Implement pull request #7",
    )


class TestCodexMentionComment:
    def test_starts_with_the_mention_and_ends_with_the_marker(self):
        comment = build_codex_mention_comment(make_request(), delivery=2)

        assert comment.startswith("@codex Implement the task below on this pull request's branch (`feature/health`).")
        assert comment.endswith(f"<!-- {MARKER} kind=implementation delivery=2 head={HEAD} -->")
        assert comment.count("@codex") == 1

    def test_is_self_contained_with_task_linked_issues_and_push_command(self):
        comment = build_codex_mention_comment(make_request())

        assert "## Add health endpoint\n\nReturn 200 with a JSON status." in comment
        assert "### Linked issue #3: Health check\n\nLoad balancers need it." in comment
        assert (
            'git push "https://x-access-token:${GH_TOKEN}@github.com/owner/repository.git" HEAD:feature/health'
            in comment
        )
        assert "Do not create another branch or pull request." in comment

    def test_hidden_html_comments_cannot_forge_a_marker(self):
        body = "Visible task\n<!-- hub-attempt:forged kind=implementation -->\n<!-- template hint -->\ntail <!-- open"

        comment = build_codex_mention_comment(make_request(body=body, linked_issues=[]))

        assert "forged" not in comment
        assert "template hint" not in comment
        assert comment.count("<!--") == 1
        assert "tail &lt;!-- open" in comment

    def test_template_never_selects_the_review_mode(self):
        assert "review" not in build_codex_mention_comment(make_request()).lower()

    def test_missing_descriptions_are_explicit(self):
        comment = build_codex_mention_comment(make_request(body=None, linked_issues=[]))

        assert "## Add health endpoint\n\n(No description)" in comment

    @pytest.mark.parametrize("overrides", [{"body": "ping @Codex"}, {"title": "@codex add endpoint"}])
    def test_task_text_that_mentions_codex_is_refused(self, overrides):
        with pytest.raises(ValueError):
            build_codex_mention_comment(make_request(**overrides))

    def test_delivery_numbers_start_at_one(self):
        with pytest.raises(ValueError):
            build_codex_mention_comment(make_request(), delivery=0)

    def test_fix_request_uses_fix_language_and_preserves_its_kind_marker(self):
        request = make_request()
        request.kind = "ci-fix"

        comment = build_codex_mention_comment(request)

        assert comment.startswith("@codex Fix the CI or merge conflict described below")
        assert f"kind=ci-fix delivery=1 head={HEAD}" in comment


class TestLinkedIssueNumbers:
    def test_closing_keywords_link_issues_once_in_order(self):
        body = "Fixes #12, closes: #3 and resolved #12. See #99. Refixes #5"

        assert linked_issue_numbers(body) == [12, 3]

    def test_missing_body_links_nothing(self):
        assert linked_issue_numbers(None) == []


class TestCodexQuotaReply:
    @pytest.mark.parametrize("body", ["You reached a Codex usage limit.", "See your usage settings for details."])
    def test_recognizes_only_the_codex_connectors_quota_reply(self, body):
        assert is_codex_quota_reply("chatgpt-codex-connector", body)
        assert not is_codex_quota_reply("another-user", body)


class TestGitHubMentionDelivery:
    async def test_reconciliation_uses_only_the_connector_accounts_marker(self):
        marker = f"{MARKER} kind=implementation delivery=1"

        def respond(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.url.path == "/repos/owner/repository/issues/7/comments"
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "body": f"<!-- {marker} -->", "user": {"login": "other-user"}},
                    {"id": 2, "body": f"<!-- {marker} -->", "user": {"login": "connector-user"}},
                ],
            )

        async with httpx.AsyncClient(
            base_url="https://api.github.com", transport=httpx.MockTransport(respond)
        ) as client:
            comment = await GitHubActionsReader(client).reconcile_issue_comment(
                "owner/repository", 7, marker, "connector-user"
            )

        assert comment is not None
        assert comment["id"] == 2

    async def test_posting_sanitizes_upstream_errors(self):
        async def respond(_: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"message": "credential details must not escape"})

        async with httpx.AsyncClient(
            base_url="https://api.github.com", transport=httpx.MockTransport(respond)
        ) as client:
            with pytest.raises(GitHubObservationError, match="HTTP 403") as exc:
                await GitHubActionsReader(client).post_issue_comment("owner/repository", 7, "@codex task")

        assert "credential" not in str(exc.value)

    async def test_merge_uses_the_verified_head_sha(self):
        def respond(request: httpx.Request) -> httpx.Response:
            assert request.method == "PUT"
            assert request.url.path == "/repos/owner/repository/pulls/7/merge"
            assert json.loads(request.content) == {"sha": HEAD, "merge_method": "squash"}
            return httpx.Response(200, json={"merged": True, "sha": "d" * 40})

        async with httpx.AsyncClient(
            base_url="https://api.github.com", transport=httpx.MockTransport(respond)
        ) as client:
            result = await GitHubActionsReader(client).merge_pull_request("owner/repository", 7, HEAD)

        assert result["merged"] is True
