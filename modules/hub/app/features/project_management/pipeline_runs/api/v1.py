from typing import Annotated
from uuid import UUID

from app.features.project_management.pipeline_runs.schemas import (
    AttachPRRequest,
    CompleteAttemptRequest,
    ExecutionAttemptList,
    ExecutionAttemptRead,
    LeaseGrant,
    LeaseMutation,
    LeaseRequest,
    PauseRunRequest,
    PipelineRunList,
    PipelineRunRead,
    PreparedImplementationAttempt,
    PrepareImplementationAttempt,
)
from app.features.project_management.pipeline_runs.usecases.lifecycle import PipelineRunUseCase
from app.features.project_management.pipelines.services import PipelineObservationService
from fastapi import APIRouter, Depends, Query, Response, status

router = APIRouter(prefix="/pipeline-runs", tags=["Pipeline Run"])


@router.get("", response_model=PipelineRunList)
async def list_pipeline_runs(
    use_case: Annotated[PipelineRunUseCase, Depends()],
    project_id: UUID | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return await use_case.list(project_id, offset, limit)


@router.get("/{run_id}", response_model=PipelineRunRead)
async def get_pipeline_run(run_id: UUID, use_case: Annotated[PipelineRunUseCase, Depends()]):
    return await use_case.get(run_id)


@router.get("/{run_id}/attempts", response_model=ExecutionAttemptList)
async def list_execution_attempts(run_id: UUID, use_case: Annotated[PipelineRunUseCase, Depends()]):
    return await use_case.list_attempts(run_id)


@router.post("/{run_id}/lease", response_model=LeaseGrant)
async def acquire_pipeline_run_lease(
    run_id: UUID, request: LeaseRequest, use_case: Annotated[PipelineRunUseCase, Depends()]
):
    return await use_case.acquire_lease(run_id, request)


@router.put("/{run_id}/lease", response_model=LeaseGrant)
async def renew_pipeline_run_lease(
    run_id: UUID, request: LeaseMutation, use_case: Annotated[PipelineRunUseCase, Depends()]
):
    return await use_case.renew_lease(run_id, request)


@router.post("/{run_id}/lease/release", status_code=status.HTTP_204_NO_CONTENT)
async def release_pipeline_run_lease(
    run_id: UUID, request: LeaseMutation, use_case: Annotated[PipelineRunUseCase, Depends()]
):
    await use_case.release_lease(run_id, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{run_id}/attempts/implementation", response_model=PreparedImplementationAttempt)
async def prepare_implementation_attempt(
    run_id: UUID,
    request: PrepareImplementationAttempt,
    use_case: Annotated[PipelineRunUseCase, Depends()],
):
    """Persist an immutable attempt before any external delegation."""
    return await use_case.prepare_implementation(run_id, request)


@router.post("/{run_id}/advance", response_model=PipelineRunRead)
async def advance_pipeline_run(
    run_id: UUID,
    use_case: Annotated[PipelineRunUseCase, Depends()],
    observer: Annotated[PipelineObservationService, Depends()],
):
    """Trigger manual run progression check (PR detection or CI verification)."""
    return await use_case.manual_advance(run_id, observer)


@router.post("/{run_id}/pause", response_model=PipelineRunRead)
async def pause_pipeline_run(
    run_id: UUID,
    use_case: Annotated[PipelineRunUseCase, Depends()],
    request: PauseRunRequest | None = None,
):
    """Pause an active pipeline run."""
    return await use_case.pause_run(run_id, request)


@router.post("/{run_id}/resume", response_model=PipelineRunRead)
async def resume_pipeline_run(
    run_id: UUID,
    use_case: Annotated[PipelineRunUseCase, Depends()],
):
    """Resume a paused pipeline run."""
    return await use_case.resume_run(run_id)


@router.post("/{run_id}/cancel", response_model=PipelineRunRead)
async def cancel_pipeline_run(
    run_id: UUID,
    use_case: Annotated[PipelineRunUseCase, Depends()],
):
    """Cancel a pipeline run."""
    return await use_case.cancel_run(run_id)


@router.post("/{run_id}/attach-pr", response_model=PipelineRunRead)
async def attach_pull_request(
    run_id: UUID,
    request: AttachPRRequest,
    use_case: Annotated[PipelineRunUseCase, Depends()],
):
    """Worker callback: attach opened PR to run and transition to awaiting_ci."""
    return await use_case.attach_pr(run_id, request)


@router.post("/{run_id}/attempts/{attempt_id}/complete", response_model=ExecutionAttemptRead)
async def complete_attempt(
    run_id: UUID,
    attempt_id: UUID,
    request: CompleteAttemptRequest,
    use_case: Annotated[PipelineRunUseCase, Depends()],
):
    """Worker callback: record attempt completion or failure."""
    return await use_case.complete_attempt(run_id, attempt_id, request)
