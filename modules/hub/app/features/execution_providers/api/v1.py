from datetime import UTC, datetime
from typing import Annotated

from app.features.execution_providers.repos import ExecutionProviderRepository
from app.features.execution_providers.schemas import (
    ExecutionProviderList,
    ExecutionProviderRead,
    SetAvailabilityRequest,
    SetEnabledRequest,
)
from app.features.execution_providers.services import ExecutionProviderService
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/execution-providers", tags=["Execution Provider"])


async def _read(provider, repo, session) -> ExecutionProviderRead:
    return ExecutionProviderRead.model_validate(provider).model_copy(
        update={
            "held_run_count": await repo.held_run_count(session, provider.id, datetime.now(UTC)),
            "effective_concurrency": ExecutionProviderService.effective_concurrency(provider),
        }
    )


@router.get("", response_model=ExecutionProviderList)
async def list_execution_providers(repo: Annotated[ExecutionProviderRepository, Depends()]):
    async with AsyncTransaction() as session:
        providers = await repo.list(session)
        return ExecutionProviderList(items=[await _read(provider, repo, session) for provider in providers])


@router.put("/{provider_key}/availability", response_model=ExecutionProviderRead)
async def set_execution_provider_availability(
    provider_key: str,
    request: SetAvailabilityRequest,
    service: Annotated[ExecutionProviderService, Depends()],
    repo: Annotated[ExecutionProviderRepository, Depends()],
):
    async with AsyncTransaction() as session:
        provider = await service.set_availability(session, provider_key, request, datetime.now(UTC))
        return await _read(provider, repo, session)


@router.delete("/{provider_key}/availability", response_model=ExecutionProviderRead)
async def clear_execution_provider_availability(
    provider_key: str,
    service: Annotated[ExecutionProviderService, Depends()],
    repo: Annotated[ExecutionProviderRepository, Depends()],
):
    async with AsyncTransaction() as session:
        provider = await service.clear_availability(session, provider_key, datetime.now(UTC))
        return await _read(provider, repo, session)


@router.put("/{provider_key}/enabled", response_model=ExecutionProviderRead)
async def set_execution_provider_enabled(
    provider_key: str,
    request: SetEnabledRequest,
    service: Annotated[ExecutionProviderService, Depends()],
    repo: Annotated[ExecutionProviderRepository, Depends()],
):
    async with AsyncTransaction() as session:
        provider = await service.set_enabled(session, provider_key, request.enabled, datetime.now(UTC))
        return await _read(provider, repo, session)
