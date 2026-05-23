from typing import Annotated

from app.features.tasks.core.schemas import TaskSpecResponse
from app.features.tasks.usecases.task_spec import GetTaskSpecUseCase
from fastapi import APIRouter, Depends, Query, status

router = APIRouter(prefix="/tasks", tags=["Task"], dependencies=[])


@router.get("/specs", status_code=status.HTTP_200_OK, response_model=list[TaskSpecResponse])
async def get_task_specs(
    use_case: Annotated[GetTaskSpecUseCase, Depends()],
    name: str | None = Query(default=None, description="Filter task specs by name (case-insensitive substring)"),
):
    """Retrieve all registered task specifications, optionally filtered by name."""
    return await use_case.execute(name=name)
