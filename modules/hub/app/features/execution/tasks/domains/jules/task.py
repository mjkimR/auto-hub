from app.features.ai_catalogs.repos import AICatalogRepository
from app.features.ai_catalogs.services import AICatalogService
from app.features.configuration.connectors.crypto import ConnectorCredentialCipher, get_credential_key_provider
from app.features.execution.tasks import task
from app.features.execution.tasks.core.context import get_task_meta
from app.features.execution.tasks.domains.jules.service import (
    JulesSessionPayload,
    JulesSessionService,
    JulesSyncPayload,
)

JULES_SESSION_TASK = "jules.session"
JULES_SYNC_TASK = "jules.sync_sessions"


def _service() -> JulesSessionService:
    return JulesSessionService(
        AICatalogService(AICatalogRepository()), ConnectorCredentialCipher(get_credential_key_provider())
    )


@task(name=JULES_SESSION_TASK)
async def start_jules_session_task(payload: JulesSessionPayload) -> None:
    """Start one Jules session when the catalog's quota admits it, after refreshing its tracked sessions."""
    meta = get_task_meta()
    if meta is None:
        raise RuntimeError(f"{JULES_SESSION_TASK} requires a schedule task context")
    await _service().start(payload, meta.config_id)


@task(name=JULES_SYNC_TASK)
async def sync_jules_sessions_task(payload: JulesSyncPayload) -> None:
    """Refresh unfinished Jules sessions so finished ones release catalog concurrency. Starts nothing."""
    await _service().sync(payload.catalog_key)
