from typing import Annotated
from uuid import UUID

from app.features.project_management.pipeline_runs.schemas import EnrollPullRequest, PipelineRunRead
from app.features.project_management.pipeline_runs.usecases.lifecycle import PipelineRunUseCase
from app.features.project_management.projects.schemas import (
    CheckRequest,
    ConnectionCheck,
    ImportScheduleRequest,
    ProjectList,
    ProjectRead,
    ProjectUpdate,
    ProjectWrite,
    TemplateRead,
)
from app.features.project_management.projects.templates import list_templates
from app.features.project_management.projects.usecases.crud import ProjectUseCase
from app.features.project_management.projects.usecases.onboarding import CheckProjectUseCase
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


@router.post("/{project_id}/runs", response_model=PipelineRunRead, status_code=201)
async def enroll_pull_request(
    project_id: UUID, data: EnrollPullRequest, use_case: Annotated[PipelineRunUseCase, Depends()]
):
    """Register one open pull request as a queued pipeline run. Reads GitHub only; posts nothing."""
    return await use_case.enroll(project_id, data)


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(project_id: UUID, data: ProjectUpdate, use_case: Annotated[ProjectUseCase, Depends()]):
    return await use_case.update(project_id, data)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: UUID, use_case: Annotated[ProjectUseCase, Depends()]):
    await use_case.delete(project_id)
    return Response(status_code=204)


@router.post("/{project_id}/check", response_model=ConnectionCheck)
async def check_project(project_id: UUID, data: CheckRequest, use_case: Annotated[CheckProjectUseCase, Depends()]):
    """Read GitHub, verify one current PR run, and identify the token's account. Never writes to GitHub."""
    return await use_case.execute(project_id, data.pull_number)
