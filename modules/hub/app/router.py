from typing import Annotated

from app.auth import verify_api_key
from app.features.dispatchers.api.v1 import router as v1_dispatchers_router
from app.features.schedule_configs.api.v1 import router as v1_schedule_configs_router
from app.features.schedule_jobs.api.v1 import router as v1_schedule_jobs_router
from app.features.system_configs.api.v1 import router as v1_system_configs_router
from app.features.tasks.api.v1 import router as v1_tasks_router
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
v1_router.include_router(v1_schedule_configs_router)
v1_router.include_router(v1_system_configs_router)
v1_router.include_router(v1_schedule_jobs_router)
v1_router.include_router(v1_dispatchers_router)
v1_router.include_router(v1_tasks_router)
router.include_router(v1_router)
