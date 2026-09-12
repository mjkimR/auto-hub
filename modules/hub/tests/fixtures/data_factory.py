"""
Deterministic test entity seeding fixtures without polyfactory.

Provides make_db, make_db_batch, make_api, and make_api_batch fixtures
using explicit, reproducible schema defaults aligned with app-testing conventions.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, get_args, get_origin
from uuid import UUID, uuid4

import pytest
from app_layer_base.base.models.mixin import Base
from app_layer_base.base.repos.base import BaseRepository
from app_testing_base import random_string, resolve_dependency
from httpx import AsyncClient
from pydantic import BaseModel
from pydantic_core import PydanticUndefined
from sqlalchemy.ext.asyncio import AsyncSession


def _generate_default_for_type(annotation: Any, field_name: str) -> Any:
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        if type(None) in args:
            return None
        if origin is list:
            return []
        if origin is dict:
            return {}
        if origin is set:
            return set()
    if annotation is str:
        return f"{field_name}_{random_string(4)}"
    if annotation is int:
        return 60 if "second" in field_name else 1
    if annotation is float:
        return 1.0
    if annotation is bool:
        return True
    if annotation is dict:
        return {}
    if annotation is list:
        return []
    if annotation is datetime:
        return datetime.now(UTC)
    if annotation is UUID:
        return uuid4()
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return next(iter(annotation))
    return None


def build_schema_instance[T: BaseModel](model_cls: type[T], **overrides: Any) -> T:
    """Build a valid, deterministic Pydantic schema instance for testing."""
    known_defaults: dict[str, Any] = {}
    cls_name = model_cls.__name__

    if cls_name == "ScheduleConfigCreate":
        known_defaults = {
            "name": f"config-{random_string(6)}",
            "task_func": "sample.task",
            "interval_seconds": 60,
            "payload": {},
        }
    elif cls_name == "ScheduleJobCreate":
        from app.features.schedule_jobs.models import ScheduleJobStatus

        known_defaults = {
            "name": f"job-{random_string(6)}",
            "status": ScheduleJobStatus.PENDING,
            "payload": {},
            "schedule_config_id": None,
            "dispatcher_run_id": None,
            "finished_at": None,
            "error_message": None,
        }
    elif cls_name == "SystemConfigCreate":
        known_defaults = {
            "name": f"sys-{random_string(6)}",
            "data": {},
        }

    values: dict[str, Any] = dict(known_defaults)
    values.update(overrides)

    for field_name, field_info in model_cls.model_fields.items():
        if field_name in values:
            continue
        if field_info.default is not PydanticUndefined:
            continue
        if field_info.default_factory is not None:
            continue

        values[field_name] = _generate_default_for_type(field_info.annotation, field_name)

    return model_cls(**values)


def _find_generic_args(repo_class: type[BaseRepository]) -> type[BaseModel]:
    """Extract generic type arguments from a BaseRepository subclass."""
    if not issubclass(repo_class, BaseRepository):
        raise ValueError(f"{repo_class.__name__} is not a subclass of BaseRepository.")
    if not hasattr(repo_class, "__orig_bases__"):
        raise ValueError(f"{repo_class.__name__} does not have __orig_bases__ attribute.")
    orig_bases = repo_class.__orig_bases__  # type: ignore
    generic_args = get_args(orig_bases[0])
    return generic_args[1]


@pytest.fixture
def make():
    """Pydantic model factory fixture."""

    def _make[T: BaseModel](model_class: type[T], _use_default: bool = False, **kwargs: Any) -> T:
        return build_schema_instance(model_class, **kwargs)

    return _make


@pytest.fixture
def make_batch():
    """Pydantic model batch factory fixture."""

    def _make_batch[T: BaseModel](
        model_class: type[T], _size: int = 3, _use_default: bool = False, **kwargs: Any
    ) -> list[T]:
        return [build_schema_instance(model_class, **kwargs) for _ in range(_size)]

    return _make_batch


@pytest.fixture
def make_db(session: AsyncSession):
    """SQLAlchemy model factory fixture using repository."""

    async def _make_db(
        repo_class_or_instance: type[BaseRepository] | BaseRepository,
        _build_kwargs: dict[str, Any] | None = None,
        _create_kwargs: dict[str, Any] | None = None,
        _use_default: bool = False,
        **kwargs: Any,
    ) -> Base:
        if not isinstance(repo_class_or_instance, type):
            repo_class = type(repo_class_or_instance)
            repo = repo_class_or_instance
        else:
            repo_class = repo_class_or_instance
            repo = resolve_dependency(repo_class_or_instance)
        create_schema_type = _find_generic_args(repo_class)
        merged_build = {**kwargs, **(_build_kwargs or {})}
        data = build_schema_instance(create_schema_type, **merged_build)
        result = await repo.create(session, data, **{**kwargs, **(_create_kwargs or {})})
        await session.commit()
        return result

    return _make_db


@pytest.fixture
def make_db_batch(session: AsyncSession):
    """SQLAlchemy model batch factory fixture using repository."""

    async def _make_db_batch(
        repo_class_or_instance: BaseRepository | type[BaseRepository],
        _size: int = 3,
        _build_kwargs: dict[str, Any] | None = None,
        _create_kwargs: dict[str, Any] | None = None,
        _use_default: bool = False,
        **kwargs: Any,
    ) -> list[Base]:
        if not isinstance(repo_class_or_instance, type):
            repo_class = type(repo_class_or_instance)
            repo = repo_class_or_instance
        else:
            repo_class = repo_class_or_instance
            repo = resolve_dependency(repo_class_or_instance)
        create_schema_type = _find_generic_args(repo_class)
        results = []
        for _ in range(_size):
            merged_build = {**kwargs, **(_build_kwargs or {})}
            data = build_schema_instance(create_schema_type, **merged_build)
            results.append(await repo.create(session, data, **{**kwargs, **(_create_kwargs or {})}))
        await session.commit()
        return results

    return _make_db_batch


@pytest.fixture
def make_api(client: AsyncClient):
    """API model factory fixture."""

    async def _make_api[T: BaseModel](
        endpoint: str, model_class: type[T], _use_default: bool = False, **kwargs: Any
    ) -> T:
        data = build_schema_instance(model_class, **kwargs)
        response = await client.post(endpoint, json=data.model_dump())
        response.raise_for_status()
        return model_class.model_validate(response.json())

    return _make_api


@pytest.fixture
def make_api_batch(client: AsyncClient):
    """API model batch factory fixture."""

    async def _make_api_batch[T: BaseModel](
        endpoint: str, model_class: type[T], _size: int = 3, _use_default: bool = False, **kwargs: Any
    ) -> list[T]:
        items = []
        for _ in range(_size):
            data = build_schema_instance(model_class, **kwargs)
            items.append(data.model_dump())
        response = await client.post(endpoint, json=items)
        response.raise_for_status()
        return [model_class.model_validate(item) for item in response.json()]

    return _make_api_batch
