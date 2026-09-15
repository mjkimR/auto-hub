from datetime import UTC, datetime
from typing import Annotated

from app.features.ai_catalogs.repos import AICatalogRepository
from app.features.ai_catalogs.schemas import (
    AICatalogList,
    AICatalogRead,
    SetAvailabilityRequest,
    SetConnectorRequest,
    SetEnabledRequest,
    UpdatePolicyConfigRequest,
)
from app.features.ai_catalogs.services import AICatalogService
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/ai-catalogs", tags=["AI Catalog"])


async def _read(catalog, repo, session) -> AICatalogRead:
    await session.refresh(catalog)
    return AICatalogRead.model_validate(catalog).model_copy(
        update={
            "held_run_count": await repo.held_run_count(session, catalog.id, datetime.now(UTC)),
            "active_dispatch_count": await repo.active_dispatch_count(session, catalog.id),
            "effective_concurrency": AICatalogService.effective_concurrency(catalog),
        }
    )


@router.get("", response_model=AICatalogList)
async def list_ai_catalogs(repo: Annotated[AICatalogRepository, Depends()]):
    async with AsyncTransaction() as session:
        catalogs = await repo.list(session)
        return AICatalogList(items=[await _read(catalog, repo, session) for catalog in catalogs])


@router.put("/{catalog_key}/availability", response_model=AICatalogRead)
async def set_ai_catalog_availability(
    catalog_key: str,
    request: SetAvailabilityRequest,
    service: Annotated[AICatalogService, Depends()],
    repo: Annotated[AICatalogRepository, Depends()],
):
    async with AsyncTransaction() as session:
        catalog = await service.set_availability(session, catalog_key, request, datetime.now(UTC))
        return await _read(catalog, repo, session)


@router.delete("/{catalog_key}/availability", response_model=AICatalogRead)
async def clear_ai_catalog_availability(
    catalog_key: str,
    service: Annotated[AICatalogService, Depends()],
    repo: Annotated[AICatalogRepository, Depends()],
):
    async with AsyncTransaction() as session:
        catalog = await service.clear_availability(session, catalog_key, datetime.now(UTC))
        return await _read(catalog, repo, session)


@router.put("/{catalog_key}/enabled", response_model=AICatalogRead)
async def set_ai_catalog_enabled(
    catalog_key: str,
    request: SetEnabledRequest,
    service: Annotated[AICatalogService, Depends()],
    repo: Annotated[AICatalogRepository, Depends()],
):
    async with AsyncTransaction() as session:
        catalog = await service.set_enabled(session, catalog_key, request.enabled, datetime.now(UTC))
        return await _read(catalog, repo, session)


@router.put("/{catalog_key}/policy-config", response_model=AICatalogRead)
async def update_ai_catalog_policy_config(
    catalog_key: str,
    request: UpdatePolicyConfigRequest,
    service: Annotated[AICatalogService, Depends()],
    repo: Annotated[AICatalogRepository, Depends()],
):
    async with AsyncTransaction() as session:
        catalog = await service.update_policy_config(session, catalog_key, request)
        return await _read(catalog, repo, session)


@router.put("/{catalog_key}/connector", response_model=AICatalogRead)
async def set_ai_catalog_connector(
    catalog_key: str,
    request: SetConnectorRequest,
    service: Annotated[AICatalogService, Depends()],
    repo: Annotated[AICatalogRepository, Depends()],
):
    async with AsyncTransaction() as session:
        catalog = await service.set_connector(session, catalog_key, request.connector_id)
        return await _read(catalog, repo, session)
