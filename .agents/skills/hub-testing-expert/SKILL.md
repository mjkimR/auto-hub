---
name: hub-testing-expert
description: Expert in writing tests for the Hub module, adhering to the Test Trophy model and specific fixtures/conventions. Use when asked to write or fix tests in the hub module.
metadata:
  version: 1.0.0
---

# Hub Testing Expert Skill

This skill provides comprehensive guidance and standards for writing high-quality tests for the Hub module. It prioritizes refactoring resilience, ROI, and consistency using the Test Trophy model.

## Core Instructions

1.  **Prioritize Test Types**:
    *   **E2E**: For critical flows and CRUD APIs.
    *   **Integration**: For core business logic and component interactions.
    *   **Unit**: Only for pure, isolated, complex business logic.
2.  **Explore Before Implementing**:
    *   Use `python scripts/show_test_structure.py hub` to see the current test directory structure.
    *   Use `python scripts/list_fixtures.py hub` to see available fixtures and their descriptions.
    *   Always check existing tests in the same module for naming and structure consistency.
3.  **Follow Directory & Naming Conventions**:
    *   Place tests in `tests/unit/`, `tests/integrate/`, or `tests/e2e/`.
    *   Use specific naming patterns like `test_<operation>_<entity>.py`.
4.  **Leverage Fixtures & Templates**:
    *   Use the canonical templates provided in the [Testing Guide](references/TESTING_GUIDE.md).
    *   Use `session` (AsyncSession) for direct DB interaction.
    *   Use `client` (AsyncClient) for E2E API tests.
    *   Use `make_db` and `make_db_batch` with **Repository classes** to create test data.
5.  **Resolve Dependencies**:
    *   Use `resolve_dependency` in Integration/Unit tests to automatically handle FastAPI dependency injection.
6.  **Validate Correctness**:
    *   Use assertion helpers from `tests/utils/assertions.py`.
    *   Use `inspect_session` to verify DB state in deletion or update tests to avoid caching issues.

## References

For detailed information on strategy, fixtures, polyfactory caveats, and best practices, refer to the full guide:
[Testing Guide](references/TESTING_GUIDE.md)

## Examples

For full, ready-to-use templates, refer to the [Canonical Test Templates](references/TESTING_GUIDE.md#12-canonical-test-templates) section in the Testing Guide.

### Integration Pattern (High ROI)
Focus on `resolve_dependency` to instantiate the business logic with a real test session.
```python
use_case = resolve_dependency(YourUseCase, state={"db": session})
result = await use_case.execute(payload)
```

### E2E Pattern (CRUD Verification)
Focus on `make_db` for setup and `client` for execution.
```python
entity = await make_db(YourRepository, name="Test")
response = await client.get(f"/api/v1/entities/{entity.id}")
assert_status_code(response, 200)
```
