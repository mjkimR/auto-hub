"""Codex PR mention payloads (docs/codex-pr-mention.md). Posting and reconciliation belong to an adapter."""

import re
from typing import Protocol

from app.features.project_management.pipeline_runs.schemas import ImplementationRequest
from pydantic import BaseModel

CODEX_MENTION = re.compile(r"@codex\b", re.IGNORECASE)
CODEX_CONNECTOR_LOGIN = "chatgpt-codex-connector"
CODEX_QUOTA_REPLY = re.compile(r"(?:usage|rate) limit|usage settings", re.IGNORECASE)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


class DispatchObservation(BaseModel):
    correlation_marker: str
    external_correlation_id: str | None = None
    external_status: str | None = None
    conversation_url: str | None = None


class ExecutionProvider(Protocol):
    async def reconcile(self, request: ImplementationRequest, delivery: int) -> DispatchObservation | None: ...

    async def dispatch(self, request: ImplementationRequest, delivery: int, body: str) -> DispatchObservation: ...


def is_codex_quota_reply(author: str | None, body: str | None) -> bool:
    """Keep the observed Codex quota wording in one conservative matcher."""
    return author == CODEX_CONNECTOR_LOGIN and bool(CODEX_QUOTA_REPLY.search(body or ""))


def _task_text(text: str | None) -> str:
    """Drop hidden HTML comments, which could carry a forged marker, and defuse an unterminated one."""
    cleaned = _HTML_COMMENT.sub("", text or "").replace("<!--", "&lt;!--").strip()
    if CODEX_MENTION.search(cleaned):
        raise ValueError("Task text must not mention Codex; enrollment rejects such pull requests")
    return cleaned


def build_codex_mention_comment(request: ImplementationRequest, *, delivery: int = 1) -> str:
    """One self-contained task comment: leading mention, task, push block, trailing marker."""
    if delivery < 1:
        raise ValueError("Delivery numbers start at 1")
    pull = request.pull_request
    sections = [
        f"@codex {'Fix the CI or merge conflict described below' if request.kind != 'implementation' else 'Implement the task below'} on this pull request's branch (`{pull.head_ref}`).",
        f"## {_task_text(pull.title)}",
        _task_text(pull.body) or "(No description)",
    ]
    for issue in pull.linked_issues:
        sections.append(f"### Linked issue #{issue.number}: {_task_text(issue.title)}")
        sections.append(_task_text(issue.body) or "(No description)")
    sections += [
        f"## Request instructions\n\n{_task_text(request.instructions)}",
        "## Ground rules\n\n"
        "- Follow the repository's AGENTS.md.\n"
        "- Stay within the task scope; leave unrelated code untouched.\n"
        "- Run the repository's required checks and make sure they pass before you push.",
        "Your environment provides network access to github.com and a `GH_TOKEN` environment variable "
        "with push rights to this repository. When your work is done, push your commit to this branch yourself:\n\n"
        "```bash\n"
        f'git push "https://x-access-token:${{GH_TOKEN}}@github.com/{request.repository}.git" HEAD:{pull.head_ref}\n'
        "```\n\n"
        "After pushing, verify with `git ls-remote` that the remote branch tip equals your commit. "
        "Do not create another branch or pull request.",
        f"<!-- {request.correlation_marker} kind={request.kind} delivery={delivery} head={pull.head_sha} -->",
    ]
    return "\n\n".join(sections)
