from app.features.pipelines.schemas import PipelineObservationConfig
from app.features.projects.repos import ProjectRepository
from app.features.projects.schemas import ProjectObservationPayload, ProjectRead
from app.features.projects.services import ProjectError, ProjectService
from app_layer_base.core.database.transaction import AsyncTransaction


async def resolve_project_observation(payload: ProjectObservationPayload) -> tuple[PipelineObservationConfig, int]:
    async with AsyncTransaction() as session:
        row = await ProjectService(ProjectRepository()).get(session, payload.project_id)
        project = ProjectRead.model_validate(row)
    if not project.enabled:
        raise ProjectError(422, "Project observation is disabled")
    return project.observation_config(payload.pull_numbers), project.revision
