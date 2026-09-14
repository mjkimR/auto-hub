from typing import Annotated

from app.auth import verify_api_key
from app.features.configuration.connectors.api.v1 import router as v1_connectors_router
from app.features.configuration.system_configs.api.v1 import router as v1_system_configs_router
from app.features.execution.dispatchers.api.v1 import router as v1_dispatchers_router
from app.features.execution.tasks.api.v1 import router as v1_tasks_router
from app.features.project_management.github_webhooks.api import router as github_webhooks_router
from app.features.project_management.pipeline_runs.api.v1 import router as v1_pipeline_runs_router
from app.features.project_management.pipelines.api.v1 import router as v1_pipelines_router
from app.features.project_management.projects.api.v1 import router as v1_projects_router
from app.features.scheduling.schedule_configs.api.v1 import router as v1_schedule_configs_router
from app.features.scheduling.schedule_jobs.api.v1 import router as v1_schedule_jobs_router
from app_layer_base.core.database.deps import get_session
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api")
v1_router = APIRouter(prefix="/v1", dependencies=[Depends(verify_api_key)])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health():
    return {"status": "ok"}


@router.get("/health/deep", status_code=status.HTTP_200_OK)
async def deep_health_check(session: Annotated[AsyncSession, Depends(get_session)]):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content="Database connection failed",
        )


# Feature routers
v1_router.include_router(v1_connectors_router)
v1_router.include_router(v1_pipelines_router)
v1_router.include_router(v1_pipeline_runs_router)
v1_router.include_router(v1_projects_router)
v1_router.include_router(v1_schedule_configs_router)
v1_router.include_router(v1_system_configs_router)
v1_router.include_router(v1_schedule_jobs_router)
v1_router.include_router(v1_dispatchers_router)
v1_router.include_router(v1_tasks_router)
router.include_router(v1_router)
# GitHub authenticates this endpoint with its HMAC signature, not Hub's API key.
router.include_router(github_webhooks_router)
