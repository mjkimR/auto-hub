from app.features.execution.tasks import task
from app.features.execution.tasks.core.log import logger
from pydantic import BaseModel


class HelloWorldPayload(BaseModel):
    message: str = "hello"


@task()
async def hello_world(payload: HelloWorldPayload) -> None:
    """Example task. Registered as 'hello_world'."""
    logger.info(payload.message)


@task(name="no_payload_task")
async def no_payload_task() -> None:
    """Example task with no payload. Registered as 'no_payload_task'."""
    logger.info("This task has no payload.")
