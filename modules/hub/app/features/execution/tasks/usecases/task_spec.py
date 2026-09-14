import functools
import inspect

from app.features.execution.tasks.core import registry
from app.features.execution.tasks.core.schemas import TaskSpecResponse
from app_layer_base.base.usecases.base import BaseUseCase
from pydantic import BaseModel


@functools.lru_cache
def _compute_task_specs() -> list[TaskSpecResponse]:
    tasks = registry.all_tasks()
    specs = []

    for name, fn in tasks.items():
        doc = inspect.getdoc(fn)
        sig = inspect.signature(fn)

        payload_schema = None
        payload_param = sig.parameters.get("payload")

        if payload_param:
            annotation = payload_param.annotation
            if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
                payload_schema = annotation.model_json_schema()

        specs.append(
            TaskSpecResponse(
                name=name,
                description=doc or "",
                payload_schema=payload_schema,
            )
        )

    return specs


class GetTaskSpecUseCase(BaseUseCase):
    async def execute(self, name: str | None = None) -> list[TaskSpecResponse]:
        specs = _compute_task_specs()
        if name:
            name_lower = name.lower()
            return [spec for spec in specs if name_lower in spec.name.lower()]
        return specs

    @classmethod
    def clear_cache(cls):
        """Clear the cached task specifications."""
        _compute_task_specs.cache_clear()
