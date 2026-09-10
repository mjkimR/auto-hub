from app.features.connectors.crypto import ConnectorCredentialCipher, get_credential_key_provider
from app.features.pipelines.repos import PipelineObservationRepository
from app.features.pipelines.schemas import PipelineObservationConfig
from app.features.pipelines.services import OBSERVATION_TASK, PipelineObservationService
from app.features.projects.repos import PROJECT_OBSERVATION_TASK
from app.features.projects.schemas import ProjectObservationPayload
from app.features.tasks import task
from app.features.tasks.core.context import get_task_meta


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
