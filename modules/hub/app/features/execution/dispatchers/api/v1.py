from typing import Annotated

from app.features.execution.dispatchers.usecases.dispatch import DispatchUseCase
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

router = APIRouter(prefix="/dispatchers", tags=["Dispatcher"], dependencies=[])


class DispatchResponse(BaseModel):
    dispatched: int


@router.post("/trigger", status_code=status.HTTP_200_OK, response_model=DispatchResponse)
async def trigger_dispatch(
    use_case: Annotated[DispatchUseCase, Depends()],
):
    """Called by an external trigger such as Google Cloud Scheduler.
    Processes due schedules using FOR UPDATE SKIP LOCKED to prevent duplicate execution.
    """
    count = await use_case.execute()
    return DispatchResponse(dispatched=count)
