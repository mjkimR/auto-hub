from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from app.features.project_management.pipeline_runs.adapters.base import AgentReply, DeliveryReceipt, DeliveryTarget
from app.features.project_management.pipeline_runs.dispatch import (
    CODEX_CONNECTOR_LOGIN,
    build_codex_mention_comment,
    is_codex_quota_reply,
)
from app.features.project_management.pipeline_runs.schemas import ImplementationRequest
from app.features.project_management.pipelines import services as pipeline_services
from app.features.project_management.pipelines.github import GitHubActionsReader
from app.features.project_management.pipelines.services import PipelineObservationService
from app.features.project_management.projects.services import ProjectError


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class CodexGithubMentionAdapter:
    """One PR mention comment per delivery, reconciled by its hidden marker; Codex replies on the PR."""

    key = "codex-github-mention"
    silent_timeout = timedelta(hours=2, minutes=5)
    silent_block_reason = "Codex did not push after a silent retry; resume manually"

    async def deliver(
        self,
        observer: PipelineObservationService,
        target: DeliveryTarget,
        request: ImplementationRequest,
        delivery_number: int,
        authorize: Callable[[], Awaitable[None]],
    ) -> DeliveryReceipt:
        auth_token = await observer.get_token(target.connector_id, "github")
        async with pipeline_services.create_github_client(auth_token) as client:
            reader = GitHubActionsReader(client)
            login = await reader.current_login()
            marker = f"{request.correlation_marker} kind={request.kind} delivery={delivery_number}"
            comment = await reader.reconcile_issue_comment(target.repository, target.pull_number, marker, login)
            if comment is None:
                # A delayed read must not authorize a write after another worker took over.
                await authorize()
                comment = await reader.post_issue_comment(
                    target.repository,
                    target.pull_number,
                    build_codex_mention_comment(request, delivery=delivery_number),
                )

        comment_id = comment.get("id")
        if comment_id is None:
            raise ProjectError(502, "GitHub mention delivery returned an incomplete comment")
        try:
            posted_at = _utc(datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00")))
        except (KeyError, AttributeError, TypeError, ValueError):
            raise ProjectError(502, "GitHub mention delivery returned an invalid creation time") from None
        return DeliveryReceipt(
            external_id=str(comment_id),
            posted_at=posted_at,
            url=str(comment.get("html_url")) if comment.get("html_url") else None,
        )

    async def collect_replies(
        self, observer: PipelineObservationService, target: DeliveryTarget, posted_at: datetime | None
    ) -> list[AgentReply]:
        comments = await observer.list_pull_comments(target.connector_id, target.repository, target.pull_number)
        if posted_at is None:
            return []
        replies: list[AgentReply] = []
        for comment in comments:
            author = comment.get("user", {}).get("login")
            comment_id = comment.get("id")
            created_at = comment.get("created_at", "")
            if author != CODEX_CONNECTOR_LOGIN or not isinstance(created_at, str):
                continue
            try:
                replied_at = _utc(datetime.fromisoformat(created_at.replace("Z", "+00:00")))
            except ValueError:
                continue
            if replied_at < posted_at:
                continue
            body = comment.get("body")
            replies.append(
                AgentReply(
                    external_id=None if comment_id is None else str(comment_id),
                    author=author,
                    replied_at=replied_at,
                    body=str(body or ""),
                    is_quota_limit=is_codex_quota_reply(author, body),
                )
            )
        return replies
