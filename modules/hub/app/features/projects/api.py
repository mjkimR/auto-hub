from typing import Annotated
from uuid import UUID

from app.features.pipeline_runs.schemas import PipelineRunAcquisition
from app.features.pipeline_runs.usecases import PipelineRunUseCase
from app.features.projects.linear import SelectActionableIssueUseCase
from app.features.projects.onboarding import CheckProjectUseCase
from app.features.projects.schemas import (
    ActionableIssueSelection,
    CheckRequest,
    ConnectionCheck,
    ImportScheduleRequest,
    ProjectList,
    ProjectRead,
    ProjectUpdate,
    ProjectWrite,
    TemplateRead,
)
from app.features.projects.templates import list_templates
from app.features.projects.usecases import ProjectUseCase
from fastapi import APIRouter, Depends, Query, Response

router = APIRouter(prefix="/projects", tags=["Project"])


@router.get("", response_model=ProjectList)
async def list_projects(
    use_case: Annotated[ProjectUseCase, Depends()], offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)
):
    return await use_case.list(offset, limit)


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(data: ProjectWrite, use_case: Annotated[ProjectUseCase, Depends()]):
    return await use_case.create(data)


@router.get("/templates", response_model=list[TemplateRead])
async def get_project_templates():
    """Versioned starter files for installation in a target repository."""
    return list_templates()


@router.post("/import_schedule", response_model=ProjectRead)
async def import_project_schedule(data: ImportScheduleRequest, use_case: Annotated[ProjectUseCase, Depends()]):
    """Atomically adopt a legacy schedule, preserving its trigger, PRs, and history."""
    return await use_case.import_schedule(data.schedule_id)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: UUID, use_case: Annotated[ProjectUseCase, Depends()]):
    return await use_case.get(project_id)


@router.get("/{project_id}/issues/actionable", response_model=ActionableIssueSelection)
async def get_actionable_issue(project_id: UUID, use_case: Annotated[SelectActionableIssueUseCase, Depends()]):
    """Select one actionable Linear issue without changing Linear or GitHub state."""
    return await use_case.execute(project_id)


@router.post("/{project_id}/runs/acquire", response_model=PipelineRunAcquisition)
async def acquire_pipeline_run(project_id: UUID, use_case: Annotated[PipelineRunUseCase, Depends()]):
    """Resume the active run or atomically acquire one actionable Linear issue."""
    return await use_case.acquire(project_id)


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(project_id: UUID, data: ProjectUpdate, use_case: Annotated[ProjectUseCase, Depends()]):
    return await use_case.update(project_id, data)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: UUID, use_case: Annotated[ProjectUseCase, Depends()]):
    await use_case.delete(project_id)
    return Response(status_code=204)


@router.post("/{project_id}/check", response_model=ConnectionCheck)
async def check_project(project_id: UUID, data: CheckRequest, use_case: Annotated[CheckProjectUseCase, Depends()]):
    """Read GitHub/Linear and verify one current PR run. Does not install CI or dispatch external work."""
    return await use_case.execute(project_id, data.pull_number)
