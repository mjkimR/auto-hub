import asyncio
from datetime import UTC, datetime

from app.common.config import get_scheduler_defaults
from app.features.configuration.connectors.crypto import ConnectorCredentialCipher, get_credential_key_provider
from app.features.execution.tasks import task
from app.features.execution.tasks.core.context import get_task_meta
from app.features.project_management.pipeline_runs.models import PipelineRunState
from app.features.project_management.pipeline_runs.repos import PipelineRunRepository
from app.features.project_management.pipeline_runs.schemas import (
    LeaseMutation,
    LeaseRequest,
    PrepareImplementationAttempt,
)
from app.features.project_management.pipeline_runs.usecases.lifecycle import PipelineRunUseCase
from app.features.project_management.pipelines.repos import PipelineObservationRepository
from app.features.project_management.pipelines.schemas import PipelineObservationConfig
from app.features.project_management.pipelines.services import OBSERVATION_TASK, PipelineObservationService
from app.features.project_management.projects.repos import (
    PROJECT_DISPATCH_TASK,
    PROJECT_OBSERVATION_TASK,
    ProjectRepository,
)
from app.features.project_management.projects.schemas import ProjectDispatchPayload, ProjectObservationPayload
from app.features.project_management.projects.services import ProjectService
from app_layer_base.core.database.transaction import AsyncTransaction


@task(name=OBSERVATION_TASK)
async def observe_pipeline_task(payload: PipelineObservationConfig) -> None:
    """Observe required GitHub Actions jobs for configured PRs and save the latest report. No external writes."""
    meta = get_task_meta()
    if meta is None:
        raise RuntimeError("pipeline.observe requires a schedule task context")
    service = PipelineObservationService(
        PipelineObservationRepository(), ConnectorCredentialCipher(get_credential_key_provider())
    )
    await service.observe_and_save(payload, meta.config_id)


@task(name=PROJECT_OBSERVATION_TASK)
async def observe_project_task(payload: ProjectObservationPayload) -> None:
    """Observe PRs using a saved project connection. No external writes."""
    meta = get_task_meta()
    if meta is None:
        raise RuntimeError("pipeline.observe_project requires a schedule task context")
    service = PipelineObservationService(
        PipelineObservationRepository(), ConnectorCredentialCipher(get_credential_key_provider())
    )
    await service.observe_project_and_save(payload, meta.config_id)


@task(name=PROJECT_DISPATCH_TASK)
async def dispatch_project_task(payload: ProjectDispatchPayload) -> None:
    """Advance ready PR runs for one project in a bounded parallel batch."""
    meta = get_task_meta()
    if meta is None:
        raise RuntimeError(f"{PROJECT_DISPATCH_TASK} requires a schedule task context")
    cipher = ConnectorCredentialCipher(get_credential_key_provider())
    pipeline_repo = PipelineObservationRepository()
    observer = PipelineObservationService(pipeline_repo, cipher)
    project_service = ProjectService(ProjectRepository())
    run_repo = PipelineRunRepository()
    run_use_case = PipelineRunUseCase(run_repo, project_service, observer)

    async with AsyncTransaction() as session:
        runs = await run_repo.list_active(
            session, payload.project_id, limit=get_scheduler_defaults().MAX_CONCURRENT_TASKS
        )
    ready = [run for run in runs if run.next_action_at is None or run.next_action_at <= datetime.now(UTC)]
    if not ready:
        return

    semaphore = asyncio.Semaphore(get_scheduler_defaults().MAX_CONCURRENT_TASKS)

    async def advance_one(run) -> None:
        async with semaphore:
            owner = f"job:{meta.run_id}:{run.id.hex[:8]}"
            if run.state == PipelineRunState.QUEUED:
                lease = await run_use_case.acquire_lease(run.id, LeaseRequest(owner=owner, ttl_seconds=120))
                try:
                    await run_use_case.prepare_implementation(
                        run.id,
                        PrepareImplementationAttempt(
                            owner=owner,
                            token=lease.token,
                            expected_run_revision=lease.run_revision,
                        ),
                    )
                finally:
                    await run_use_case.release_lease(run.id, LeaseMutation(owner=owner, token=lease.token))
            elif run.state in (
                PipelineRunState.DISPATCHING,
                PipelineRunState.IMPLEMENTING,
                PipelineRunState.AWAITING_CI,
            ):
                lease = await run_use_case.acquire_lease(run.id, LeaseRequest(owner=owner, ttl_seconds=120))
                try:
                    if run.state == PipelineRunState.DISPATCHING:
                        await run_use_case.dispatch_implementation(run.id, owner=owner, token=lease.token)
                    else:
                        await run_use_case.advance_run(run.id, owner=owner, token=lease.token, observer=observer)
                finally:
                    await run_use_case.release_lease(run.id, LeaseMutation(owner=owner, token=lease.token))

    await asyncio.gather(*(advance_one(run) for run in ready))
