import pytest
from app.features.execution.tasks.core.registry import (
    _registry,
    _wrap_with_payload_adapter,
    all_tasks,
    autodiscover,
    get,
    task,
)
from pydantic import BaseModel


# Clean up registry before and after tests
@pytest.fixture(autouse=True)
def clean_registry():
    _registry.clear()
    yield
    _registry.clear()


class DummyPayload(BaseModel):
    id: int


def test_task_decorator_duplicate_name():
    @task(name="dup_task")
    async def dummy1():
        pass

    with pytest.raises(ValueError) as exc:

        @task(name="dup_task")
        async def dummy2():
            pass

    assert "is already registered" in str(exc.value)


async def test_wrap_with_payload_adapter_no_params():
    async def task_func():
        return "success"

    wrapped = _wrap_with_payload_adapter(task_func)
    result = await wrapped(payload={"ignored": "data"})
    assert result == "success"


async def test_wrap_with_payload_adapter_with_payload_param():
    async def task_func(payload: DummyPayload):
        return payload.id

    wrapped = _wrap_with_payload_adapter(task_func)

    # Passing dict should convert to DummyPayload
    result1 = await wrapped(payload={"id": 123})
    assert result1 == 123

    # Passing DummyPayload should work directly
    result2 = await wrapped(payload=DummyPayload(id=456))
    assert result2 == 456


def test_wrap_with_payload_adapter_no_payload_param():
    async def task_func(wrong_param):
        pass

    with pytest.raises(TypeError) as exc:
        _wrap_with_payload_adapter(task_func)
    assert "has parameters but no 'payload' parameter" in str(exc.value)


def test_wrap_with_payload_adapter_wrong_annotation():
    async def task_func(payload: dict):
        pass

    with pytest.raises(TypeError) as exc:
        _wrap_with_payload_adapter(task_func)
    assert "is not a Pydantic BaseModel subclass" in str(exc.value)


def test_wrap_with_payload_adapter_missing_annotation():
    async def task_func(payload):
        pass

    with pytest.raises(TypeError) as exc:
        _wrap_with_payload_adapter(task_func)
    assert "is not a Pydantic BaseModel subclass" in str(exc.value)


def test_get_not_found():
    with pytest.raises(KeyError) as exc:
        get("non_existent_task")
    assert "is not registered" in str(exc.value)


def test_all_tasks():
    @task(name="task1")
    async def t1():
        pass

    @task(name="task2")
    async def t2():
        pass

    tasks = all_tasks()
    assert "task1" in tasks
    assert "task2" in tasks
    assert len(tasks) == 2


def test_autodiscover_missing_package():
    with pytest.raises(ImportError) as exc:
        autodiscover("missing_dummy_package_for_test")
    assert "Failed to autodiscover tasks in package" in str(exc.value)


def test_autodiscover_valid_package():
    # Discover the dummy package created earlier
    autodiscover("tests.unit.dummy_pkg")

    tasks = all_tasks()
    assert "dummy_discovered_task" in tasks


def test_autodiscover_default_package(monkeypatch):
    import app.features.execution.tasks.core.registry as registry_module

    # We patch _import_submodules to avoid scanning actual files and just see if it's called
    # with the correct default directory and package.
    calls = []

    def mock_import_submodules(package_dir, package_name):
        calls.append((package_dir, package_name))

    monkeypatch.setattr(registry_module, "_import_submodules", mock_import_submodules)

    autodiscover()

    assert len(calls) == 1
    # Check that it uses the parent dir
    assert str(registry_module.Path(registry_module.__file__).parent.parent) in calls[0][0]
    # Check that it uses the expected default package name
    assert calls[0][1] == "app.features.execution.tasks"


def test_get_success():
    @task(name="task_to_get")
    async def t():
        pass

    retrieved = get("task_to_get")
    assert retrieved is not None
