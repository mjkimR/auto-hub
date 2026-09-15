from uuid import UUID

from app.features.ai_catalogs.repos import AICatalogRepository
from app.features.project_management.pipeline_runs.adapters.base import ExecutionAdapter
from app.features.project_management.pipeline_runs.adapters.codex_github_mention import CodexGithubMentionAdapter
from app.features.project_management.projects.services import ProjectError
from sqlalchemy.ext.asyncio import AsyncSession

_ADAPTERS: dict[str, ExecutionAdapter] = {
    CodexGithubMentionAdapter.key: CodexGithubMentionAdapter(),
}
# Adapters whose catalog kinds exist but cannot deliver pull request work yet. Resolution runs before catalog
# admission, so a run on such a catalog fails without consuming its quota.
_NOT_IMPLEMENTED: dict[str, str] = {
    # Jules cannot push to an existing pull request branch; its catalogs are meant for scheduled report and
    # hygiene sessions rather than the pull request pipeline.
    "jules-api": "Jules pull request delivery is not implemented",
}


def supports_pipeline_delivery(adapter: str) -> bool:
    return adapter in _ADAPTERS


async def resolve_execution_adapter(session: AsyncSession, catalog_id: UUID) -> ExecutionAdapter:
    catalog = await AICatalogRepository().get(session, catalog_id)
    if catalog is None:
        raise ProjectError(409, "AI catalog was removed")
    if (reason := _NOT_IMPLEMENTED.get(catalog.adapter)) is not None:
        raise ProjectError(501, reason)
    adapter = _ADAPTERS.get(catalog.adapter)
    if adapter is None:
        raise ProjectError(409, f"AI catalog adapter '{catalog.adapter}' is not supported")
    return adapter
