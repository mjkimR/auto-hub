# Testing Guide for Hub Module

This guide outlines the conventions and best practices for writing tests within the Hub module. Adhering to these
guidelines ensures consistency, maintainability, and clarity across our test suite.

## 0. Infrastructure Discovery

To understand the current state of the test environment, always use the following discovery scripts located in the root
`scripts/` directory:

- **Show Test Directory Structure**:
  ```bash
  python scripts/show_test_structure.py hub
  ```
- **List Available Fixtures**:
  ```bash
  python scripts/list_fixtures.py hub
  ```

---

## 1. Test Strategy & Priorities

... (rest of section 1) ...

---

## 2. Test Directory Structure

Tests are organized by their scope and the module they belong to. Since the structure evolves, use the discovery script
mentioned in Section 0 to see the current layout.

The high-level organization is as follows:

- **`unit/`**:
    - **Purpose**: Tests individual components (e.g., use cases, services, repositories) in isolation.
    - **Characteristics**: Heavily relies on mocking dependencies to ensure only the target component's logic is tested.
      The database is typically mocked or not involved.
    - **Naming**: `test_<component_name>_usecases.py`, `test_<component_name>_services.py`, etc.

- **`integrate/`**:
    - **Purpose**: Tests the interaction between several components, typically involving the database.
    - **Characteristics**: Uses a real database session (provided by the `session` fixture). Dependencies _within_ the
      tested flow are usually real, while external services might still be mocked.
    - **Naming**: `test_<operation>_<entity>.py` (e.g., `test_create_task.py`).

- **`e2e/`**:
    - **Purpose**: Tests the entire application flow from the API endpoint down to the database.
    - **Characteristics**: Uses an HTTP client (`client` fixture) to make requests to the FastAPI application. Involves
      the full stack, including routing, dependency injection, services, and the database.
    - **Naming**: `test_<entity>_api.py`.

## 3. Naming Conventions

- **Test Files**:
    - **Unit/E2E**: `test_<module_or_submodule_name>_<scope>.py` (e.g., `test_task_histories_api.py`).
    - **Integration (Preferred)**: `test_<operation>_<entity>.py` (e.g., `test_create_task.py`,
      `test_update_task_tag.py`).
- **Test Classes**: `Test<Operation><Entity>` (e.g., `TestCreateTask`, `TestUpdateTaskTag`).
- **Test Functions**: `test_<action_being_tested>_<expected_outcome>` (e.g., `test_create_task_history_success`).

## 4. Fixtures Usage

We leverage a rich set of pytest fixtures defined in `tests/conftest.py` and `tests/fixtures/`.

- **`session: AsyncSession`**: (from `tests/fixtures/db.py`)
    - Provides an asynchronous SQLAlchemy session connected to the test database.
    - **Use in**: Integration and E2E tests (implicitly by the app/client setup, or explicitly for direct DB
      interaction).
    - **Behavior**: Data isolation strategy differs by backend and marker —
      see [Section 11](#11-data-isolation-strategy--session-caching) for details.

- **`client: AsyncClient`**: (from `tests/fixtures/clients.py`)
    - An `httpx.AsyncClient` configured to interact with the FastAPI application directly, bypassing network calls. It's
      pre-configured to use the test database session.
    - **Use in**: E2E tests for making API requests.

- **`make: Callable`**: (from `tests/fixtures/data_factory.py`)
    - A factory for creating Pydantic models. Does NOT interact with the database.
    - **Usage**: `make(MyPydanticSchema, field_name="value")`

- **`make_batch: Callable`**: (from `tests/fixtures/data_factory.py`)
    - A factory for creating a batch of Pydantic models. Does NOT interact with the database.
    - **Usage**: `make_batch(MyPydanticSchema, _size=5, field_name="value")`

- **`make_db: Callable`**: (from `tests/fixtures/data_factory.py`)
    - A factory for creating SQLAlchemy models via Repository, adding them to the test database session.
    - **Usage**: `await make_db(MyRepository, field_name="value")` or `await make_db(repo_instance, field_name="value")`
    - Takes a Repository class or instance, automatically extracts the CreateSchema type from the repository's generic
      arguments.
    - Returns the created SQLAlchemy model instance after saving to the database.
    - **Parameters**:
        - `_build_kwargs`: Extra keyword arguments passed to `factory.build()` (schema construction step)
        - `_create_kwargs`: Extra keyword arguments passed to `repo.create()` (DB persistence step)
        - `_use_default`: If `True`, uses the schema's default values instead of random generation (default: `False`)
        - `**kwargs`: Fields to override in the factory (applied to both build and create steps)

- **`make_db_batch: Callable`**: (from `tests/fixtures/data_factory.py`)
    - A factory for creating a batch of SQLAlchemy models via Repository and adding them to the test database session.
    - **Usage**: `await make_db_batch(MyRepository, _size=5, field_name="value")`
    - Takes a Repository class or instance, automatically extracts the CreateSchema type from the repository's generic
      arguments.
    - Returns a list of created SQLAlchemy model instances.
    - **Parameters**:
        - `_size`: Number of models to create (default: `3`)
        - `_build_kwargs`: Extra keyword arguments passed to `factory.batch()`
        - `_create_kwargs`: Extra keyword arguments passed to `repo.create()`
        - `_use_default`: If `True`, uses the schema's default values instead of random generation (default: `False`)
        - `**kwargs`: Fields to override in the factory (applied to both build and create steps)

- **`make_api: Callable`**: (from `tests/fixtures/data_factory.py`)
    - A factory that creates a resource by calling an API endpoint (POST) and returns the response as a Pydantic model.
    - **Usage**: `await make_api("/api/v1/users", UserRead, name="test")`
    - **Parameters**:
        - `endpoint`: API endpoint path to POST to
        - `model_class`: Pydantic model class used for both request body generation and response parsing
        - `_use_default`: If `True`, uses the schema's default values (default: `False`)
        - `**kwargs`: Fields to override in the generated request body

- **`make_api_batch: Callable`**: (from `tests/fixtures/data_factory.py`)
    - A factory that creates multiple resources by calling an API batch endpoint and returns the responses as Pydantic
      models.
    - **Usage**: `await make_api_batch("/api/v1/users/batch", UserRead, _size=3, name="test")`
    - **Parameters**:
        - `endpoint`: API endpoint path to POST batch payload to
        - `model_class`: Pydantic model class used for both request body generation and response parsing
        - `_size`: Number of models to create (default: `3`)
        - `_use_default`: If `True`, uses the schema's default values (default: `False`)
        - `**kwargs`: Fields to override in the generated request bodies

## 5. Assertion Helpers (`tests/utils/assertions.py`)

Always prefer using the assertion helpers provided in `tests/utils/assertions.py` for common checks:

- **`assert_status_code(response, expected_status)`**: Checks HTTP status code.
- **`assert_json_contains(response, expected_dict)`**: Checks if a JSON response contains specific key-value pairs.
- **`assert_paginated_response(response, min_items=0)`**: Validates the structure of a paginated API response.
- **`assert_error_response(response, status_code, error_type=None)`**: Validates the structure of an API error response.
- **`assert_model_fields(obj, expected_dict)`**: Checks specific fields of a Pydantic or SQLAlchemy model object.

## 6. Mocking (for Unit Tests)

For unit tests, use `unittest.mock` or `pytest-mock` to isolate the component under test.

- Mock dependencies injected via FastAPI's `Depends` (e.g., services, repositories).
- Use `AsyncMock` for async functions.
- Configure `return_value` or `side_effect` for mock objects to simulate behavior.

## 7. Dependency Resolution Helper (`resolve_dependency`)

### 7.1 Purpose

The `resolve_dependency` function (located in `tests/utils/fastapi.py`) is a test utility that automatically resolves
FastAPI dependency injection trees. This eliminates the need to manually instantiate services, repositories, and use
cases with their dependencies.

### 7.2 Key Benefits

- **Automatic Dependency Resolution**: Recursively resolves all `Depends()` declarations in constructors
- **Cleaner Test Code**: No need to manually create dependency chains
- **Refactoring Resilience**: Tests don't break when you add/remove dependencies
- **Flexibility**: Supports overriding specific dependencies with mocks when needed

### 7.3 Basic Usage

**Before (Manual Instantiation):**

```python
# ❌ Manually creating all dependencies
service = ScheduleConfigService(repo=None)
use_case = CreateScheduleConfigUseCase(service=service)
```

**After (Using resolve_dependency):**

```python
# ✅ Automatic dependency resolution
from tests.utils.fastapi import resolve_dependency

use_case = resolve_dependency(CreateScheduleConfigUseCase)
```

### 7.4 Advanced Usage: Overriding Dependencies

For integration tests where you need to inject specific objects (e.g., mock session, test database):

```python
from tests.utils.fastapi import resolve_dependency

# Override specific dependencies
use_case = resolve_dependency(
    CreateSystemConfigUseCase,
    state={"db": session},  # Inject request.state values
    overrides={get_db: mock_session}  # Replace specific dependency functions
)
```

### 7.5 When to Use

- **✅ DO use** in Integration and Unit tests when instantiating services/use cases
- **✅ DO use** when you want to test with real dependency chains
- **❌ DON'T use** in E2E tests (use `client` fixture instead, which handles DI automatically)
- **❌ DON'T use** if you need to mock ALL dependencies (use direct mocking instead)

### 7.6 How It Works

The function inspects the target class/function signature and:

1. Checks for `overrides` dictionary first (highest priority)
2. Detects `Request` objects and injects `MockRequest` with state
3. Resolves `Annotated[Type, Depends(...)]` patterns
4. Resolves `Depends(...)` default values
5. Recursively resolves nested dependencies
6. Returns a fully instantiated object

For more details, see the implementation in `tests/utils/fastapi.py`.

## 8. Guide for AI (When Requesting New Tests)

When asking the AI to write new tests, please provide the following information:

- **Target Module/Resource**: Clearly specify which part of the application needs testing (e.g.,
  `app/features/schedule_configs`, `app/features/schedule_jobs`, `app/features/system_configs`,
  `app/features/dispatchers`).
- **Test Type**: Specify whether you need `unit`, `integrate`, or `e2e` tests. If unsure, describe the scope, and the AI
  can recommend.
- **Endpoints/Functions to Test**: For E2E, list the HTTP methods and paths (e.g., `POST /api/v1/schedule-configs`). For
  unit/integration, specify the class and method (e.g., `CreateScheduleConfigUseCase.execute`).
- **Expected Behavior**: Describe the successful outcomes, including expected data, status codes, and database changes.
- **Edge Cases/Error Scenarios**: Provide details on invalid inputs, missing resources, authorization failures, or other
  error conditions, along with their expected error responses.
- **Existing Dependencies**: Mention any special setup required, e.g., "This test requires an existing ScheduleConfig."
- **Special Data Needs**: If the test requires specific data values or relationships, describe them.

### Example Request for AI:

"Please create an Integration test for `app/features/schedule_configs`.
Test the `CreateScheduleConfigUseCase.execute` method.
**Expected Success**:

- Creates a new schedule config with a valid cron expression.
- Returns the created `ScheduleConfig` model instance.
  **Edge Cases**:
- Attempting to create a schedule config without either `cron_expression` or `interval_seconds` should raise a
  validation error.
- Attempting to create a schedule config with both `cron_expression` and `interval_seconds` set should raise a
  validation error."

### E2E Test Best Practices (Important!)

When writing E2E API tests, follow these critical conventions:

1. **API Path Prefix**: All API paths MUST start with `/api/v[version]/...`

   ```python
   # ✅ Correct
   response = await client.post("/api/v1/schedule-configs", ...)

   # ❌ Wrong
   response = await client.post("/schedule-configs", ...)
   ```

2. **Use Repository Classes in `make_db`, NOT SQLAlchemy Models directly**

   ```python
   # ✅ Correct - Use Repository class for DB fixtures
   from app.features.schedule_configs.repos import ScheduleConfigRepository
   config: ScheduleConfig = await make_db(ScheduleConfigRepository, name="Test Schedule", task_func="tasks.example", interval_seconds=60)

   # ✅ Also correct - Use Repository instance
   repo = resolve_dependency(ScheduleConfigRepository)
   config: ScheduleConfig = await make_db(repo, name="Test Schedule", task_func="tasks.example", interval_seconds=60)

   # ❌ Wrong - Don't use Pydantic schemas with make_db
   from app.features.schedule_configs.schemas import ScheduleConfigRead  # Pydantic schema
   config: ScheduleConfigRead = await make_db(ScheduleConfigRead, ...)  # This will fail!
   ```

3. **Parent Resource Dependencies**: Always create required parent resources (e.g., ScheduleConfig before ScheduleJob)

   ```python
   # ✅ Correct - Create full dependency chain using Repository classes
   from app.features.schedule_configs.repos import ScheduleConfigRepository
   from app.features.schedule_jobs.repos import ScheduleJobRepository

   config: ScheduleConfig = await make_db(ScheduleConfigRepository, name="My Schedule", task_func="tasks.example", interval_seconds=60)
   job: ScheduleJob = await make_db(ScheduleJobRepository, schedule_config_id=config.id, ...)
   ```

4. **DELETE Response Validation**: Check the `identity` field, not just the message

   ```python
   # ✅ Correct - Verify identity field
   response = await client.delete(f"/api/v1/schedule-configs/{config.id}")
   assert_status_code(response, 200)
   response_json = response.json()
   assert "message" in response_json
   assert response_json["identity"] == str(config.id)  # Verify the deleted resource ID

   # ❌ Wrong - Only checking if ID is in message string
   assert str(config.id) in response_json["message"]  # Too vague
   ```

## 9. Polyfactory Random Generation — Important Caveats

The `make`, `make_batch`, `make_db`, and `make_db_batch` fixtures use **polyfactory** under the hood to auto-generate
data. By default, every field is filled with a **random value**, which has a few important implications.

### 9.1 Intermittent Test Failures Due to Random Generation

Randomly generated values can occasionally violate business rules or fail DB constraints (unique, length, format, etc.),
causing tests to **fail intermittently**.

```python
# ⚠️ Risky - cron_expression is generated as a random string and may be invalid
config = await make_db(ScheduleConfigRepository)

# ✅ Safe - explicitly specify fields that have format/value constraints
config = await make_db(ScheduleConfigRepository, cron_expression="*/5 * * * *")
```

> ⚠️ **If you experience intermittent failures**, check whether any fields used in the test have format or range
> constraints and make sure they are explicitly specified.

### 9.2 Controlling Random Generation with `_use_default`

Passing `_use_default=True` instructs polyfactory to use the **default values (`default` / `default_factory`)** defined
in the schema instead of generating random ones. For simple read/select scenarios this usually doesn't matter, but it is
especially useful when testing **complex business logic** that requires predictable, well-defined input values.

```python
# Use schema defaults and only override fields relevant to the business logic under test
config = await make_db(
    ScheduleConfigRepository,
    _use_default=True,
    cron_expression="0 9 * * 1-5",  # override only what matters for the assertion
)
```

| Situation                                       | Recommended Approach                           |
|-------------------------------------------------|------------------------------------------------|
| Data just needs to exist (e.g., list/get tests) | Random generation (default)                    |
| Fields with format or range constraints         | Explicitly pass via `**kwargs`                 |
| Complex business logic / calculation assertions | `_use_default=True` + override relevant fields |
| Fields with DB unique constraints               | Always specify explicitly                      |

### 9.3 Safe Patterns for Random Generation

```python
# ✅ Explicitly specify fields that drive business logic or branching
job = await make_db(
    ScheduleJobRepository,
    _use_default=True,
    schedule_config_id=config.id,  # always specify FK
    status="pending",  # specify fields used in conditional logic
)

# ✅ Simple DB fixture where only existence matters
configs = await make_db_batch(ScheduleConfigRepository, _size=3, task_func="tasks.example")
```

---

## 10. Common Pitfalls / Best Practices

- **Avoid over-mocking in integration/E2E tests**: Only mock external systems that are truly outside the scope of the
  integration.
- **Don't test framework specifics**: Avoid testing FastAPI's routing or Pydantic's validation directly; assume the
  framework works correctly.
- **Make tests readable**: Use clear variable names, comments where necessary, and separate test stages (Given, When,
  Then).
- **Test data setup**: Use `make_db` and `make_db_batch` with Repository classes (not SQLAlchemy models) to create
  realistic but minimal test data. The factory automatically extracts the CreateSchema from the repository's generic
  arguments. Avoid hardcoding IDs unless absolutely necessary.
- **Clean up**: The `session` fixture automatically handles DB cleanup — either by rolling back the outer transaction (
  PostgreSQL default, savepoint strategy) or by running a TRUNCATE after the test (SQLite always, or PostgreSQL with
  `@pytest.mark.real_commit`). Explicit cleanup is rarely needed. For file system or other external resources, ensure
  proper teardown.
- **Async test functions**: All test functions MUST be defined as `async def`. Do **NOT** add the `@pytest.mark.asyncio`
  decorator — asyncio mode is configured globally (`asyncio_mode = "auto"` in `pyproject.toml`), so the decorator is
  unnecessary and should be omitted.

  ```python
  # ✅ Correct
  async def test_create_entity_success(session):
      ...

  # ❌ Wrong - decorator is redundant and must not be used
  @pytest.mark.asyncio
  async def test_create_entity_success(session):
      ...
  ```

## 11. Data Isolation Strategy & Session Caching

### 11.1 Data Isolation Strategies

The `session` fixture uses one of two strategies to isolate test data:

| Condition                               | Strategy                 | How it works                                                                                                                                                                                      |
|-----------------------------------------|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| PostgreSQL (default)                    | **Savepoint / Rollback** | Opens a single connection with an outer transaction. `session.commit()` only creates a savepoint internally — no real DB commit. After the test the outer transaction is rolled back.             |
| SQLite (always)                         | **TRUNCATE**             | Real commits are allowed. All tables are truncated after each test.                                                                                                                               |
| PostgreSQL + `@pytest.mark.real_commit` | **TRUNCATE**             | Real commits are allowed. All tables are truncated after each test. Use this when an external component (e.g. a background task or service spawning its own session) must observe committed data. |

### 11.2 When to Use `@pytest.mark.real_commit`

Mark a test class or function with `@pytest.mark.real_commit` when the code under test opens its **own** database
session/connection internally and therefore cannot see data that hasn't been truly committed.

```python
@pytest.mark.integrate
@pytest.mark.real_commit  # ← required: service spawns its own session
class TestDispatchJobs:
    async def test_dispatch_creates_job(self, session, ...):
        ...
```

> **Do NOT** add `@pytest.mark.real_commit` to ordinary integration tests — the savepoint strategy is faster and
> cleaner.

### 11.3 Session Identity Map Cache — Use `session.expire_all()`

> ⚠️ **Critical for `real_commit` tests**: The `session` object holds a SQLAlchemy **Identity Map** (in-memory cache).
> After the code under test commits changes on its own session, your test `session` still holds the **old, stale version**
> of those objects.

**The Solution**:
Call `session.expire_all()` before re-querying. This clears all cached state and forces the next access to fetch fresh
data from the database.

> ⚠️ **Save any attribute values you need *before* calling `expire_all()`.** After `expire_all()`, accessing an
> attribute on an expired object causes SQLAlchemy to issue a lazy DB reload for that object. This results in unnecessary
> queries or, depending on the session state, may raise an exception. Always capture values like `id` into local variables
**before** calling `expire_all()`.

**Example (Delete Test):**

```python
# ❌ Bad: session cache may return the stale (non-deleted) object
await delete_use_case.execute(config.id, context=context)
db_config = await session.get(SystemConfig, config.id)
assert db_config is None  # May fail due to cache

# ✅ Good: expire all cached objects, then re-query
config_id = config.id  # save id before expiry
session.expire_all()
db_config = await session.get(SystemConfig, config_id)
assert db_config is None
```

**Example (Update Test):**

```python
# ✅ expire_all to reload updated fields
config_id = config.id  # save id before expiry
await update_use_case.execute(config_id, update_data, ...)
session.expire_all()
db_config = await session.get(SystemConfig, config_id)
assert db_config.name == update_data["name"]
```

> **Note**: For non-`real_commit` (savepoint) tests you normally don't need `session.expire_all()` because the test
> session *is* the same session the application code uses — both share the same Identity Map and the same transaction.

---

## 12. Canonical Test Templates

Use these templates as a starting point for new tests to ensure consistency and high ROI.

### 12.1 Integration Test Template

Integration tests focus on the interaction between UseCases/Services and the Repository/Database.

```python
from tests.utils.fastapi import resolve_dependency
from tests.utils.assertions import assert_model_fields
from app.features.your_module.usecases.create_something import CreateSomethingUseCase
from app.features.your_module.repos import YourRepository


async def test_create_entity_success(session):
    # 1. Setup - Resolve dependencies with the test session
    use_case = resolve_dependency(CreateSomethingUseCase, state={"db": session})

    # 2. Execute - Perform the action
    data = {"name": "Test Entity", "value": 123}
    result = await use_case.execute(data)

    # 3. Verify - Check result and DB state
    assert result.name == "Test Entity"
    assert_model_fields(result, data)

    # Verify persistence using the same session
    saved_entity = await session.get(YourModel, result.id)
    assert saved_entity is not None
```

**When the code under test commits on its own session** (e.g. a service that opens an internal session), add
`@pytest.mark.real_commit` and use `session.expire_all()` before re-querying:

```python
@pytest.mark.integrate
@pytest.mark.real_commit
class TestDispatchJobs:
    async def test_dispatch_creates_job(self, session, make_db):
        # 1. Setup
        use_case = resolve_dependency(DispatchUseCase, state={"db": session})
        config = await make_db(ScheduleConfigRepository, ...)

        # 2. Execute
        await use_case.execute(...)

        # 3. Verify - expire cache, then re-query
        entity_id = config.id
        session.expire_all()
        updated = await session.get(YourModel, entity_id)
        assert updated.status == "done"
```

### 12.2 E2E Test Template

E2E tests verify the full API stack. They are the primary tool for CRUD validation.

> ⚠️ E2E tests call the real API server which commits data using its own session. Therefore E2E test classes **must** be
> marked with `@pytest.mark.real_commit`.

```python
from tests.utils.assertions import assert_status_code, assert_json_contains
from app.features.your_module.repos import YourRepository


@pytest.mark.e2e
@pytest.mark.real_commit
class TestYourEntityAPI:
    async def test_get_entity_api(self, client, make_db):
        # 1. Setup - Create test data using make_db and Repository
        entity = await make_db(YourRepository, name="Target Entity")

        # 2. Execute - Call the API
        response = await client.get(f"/api/v1/your-entities/{entity.id}")

        # 3. Verify - Use assertion helpers
        assert_status_code(response, 200)
        assert_json_contains(response, {
            "id": str(entity.id),
            "name": "Target Entity"
        })
```

If you need to inspect DB state after an API call (e.g. after a POST that triggers a background write), use
`session.expire_all()` before re-querying:

```python
    async def test_create_entity_persists(self, client, session):
    response = await client.post("/api/v1/your-entities", json={"name": "New"})
    assert_status_code(response, 201)
    entity_id = response.json()["id"]

    session.expire_all()
    saved = await session.get(YourModel, entity_id)
    assert saved is not None
```

### 12.3 Consistency Check

Before submitting a new test:

1. **Run discovery**: `python scripts/show_test_structure.py hub` and `python scripts/list_fixtures.py hub`.
2. **Locate similar tests**: Find an existing test for a similar feature (e.g., another CRUD API).
3. **Align style**: Match the existing test's imports, variable naming (e.g., `config` vs `cfg`), and assertion style.
4. **Verify**: Run the new test and ensure it passes cleanly without side effects.
