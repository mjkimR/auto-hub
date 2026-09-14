from typing import Annotated
from uuid import UUID

from app.features.project_management.pipelines.github import GitHubObservationError
from app.features.project_management.pipelines.schemas import PipelineObservation, PipelineObservationConfig
from app.features.project_management.pipelines.services import PipelineConfigurationError
from app.features.project_management.pipelines.usecases.observation import (
    GetPipelineObservationUseCase,
    InspectPipelineUseCase,
)
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/pipelines", tags=["Pipeline"])


@router.post("/inspect", response_model=PipelineObservation)
async def inspect_pipeline(
    config: PipelineObservationConfig,
    use_case: Annotated[InspectPipelineUseCase, Depends()],
) -> PipelineObservation:
    """Inspect CI without creating PRs, dispatching workflows, posting comments, or saving state."""
    try:
        return await use_case.execute(config)
    except PipelineConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except GitHubObservationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@router.get("/observations/{schedule_id}", response_model=PipelineObservation)
async def get_pipeline_observation(
    schedule_id: UUID,
    use_case: Annotated[GetPipelineObservationUseCase, Depends()],
) -> PipelineObservation:
    """Return the last successful observation, not live CI evidence or a merge authorization."""
    report = await use_case.execute(schedule_id)
    if report is None:
        raise HTTPException(status_code=404, detail="No observation for this schedule configuration")
    return report
