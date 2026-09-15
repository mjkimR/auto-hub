from app.features.ai_catalogs.models import AICatalog, AICatalogKind
from app.features.ai_catalogs.policies.base import QuotaPolicy
from app.features.ai_catalogs.policies.codex_window import CodexWindowPolicy
from app.features.ai_catalogs.policies.daily_quota import DailyQuotaPolicy
from app.features.ai_catalogs.repos import AICatalogRepository
from app.features.project_management.projects.services import ProjectError

_POLICIES: dict[str, QuotaPolicy] = {
    AICatalogKind.CODEX: CodexWindowPolicy(),
    AICatalogKind.JULES: DailyQuotaPolicy(AICatalogRepository()),
}


def find_quota_policy(catalog: AICatalog) -> QuotaPolicy | None:
    return _POLICIES.get(catalog.kind)


def quota_policy_for(catalog: AICatalog) -> QuotaPolicy:
    policy = find_quota_policy(catalog)
    if policy is None:
        raise ProjectError(409, f"AI catalog kind '{catalog.kind}' has no quota policy")
    return policy
