from app.features.execution.tasks.core import registry
from app.features.execution.tasks.usecases.task_spec import GetTaskSpecUseCase
from pydantic import BaseModel


class MockPayload(BaseModel):
    name: str
    age: int = 20


async def mock_task(payload: MockPayload):
    """This is a mock task."""
    pass


async def test_get_task_spec_use_case():
    # Force register a task for testing
    registry.task(name="mock_task")(mock_task)

    use_case = GetTaskSpecUseCase()
    use_case.clear_cache()
    specs = await use_case.execute()

    mock_spec = next((s for s in specs if s.name == "mock_task"), None)
    assert mock_spec is not None
    assert mock_spec.description == "This is a mock task."
    assert mock_spec.payload_schema is not None
    assert mock_spec.payload_schema["title"] == "MockPayload"
    assert "name" in mock_spec.payload_schema["properties"]
    assert "age" in mock_spec.payload_schema["properties"]
