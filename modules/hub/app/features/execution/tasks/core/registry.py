import functools
import importlib
import inspect
import pkgutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_registry: dict[str, Callable[..., Any]] = {}


def _wrap_with_payload_adapter(fn: Callable) -> Callable:
    """Wrap an async task function so that a raw dict payload is automatically
    coerced into the declared Pydantic model before the function is called.

    - No parameters at all → wrapped to absorb any kwargs dispatcher passes (e.g. payload=...).
    - payload: <BaseModel subclass> → registered with model_validate adapter.
    - Has parameters but no 'payload' → TypeError raised.
    - payload: <other type> → TypeError raised.
    """
    sig = inspect.signature(fn)
    payload_param = sig.parameters.get("payload")

    # No parameters at all: wrap to absorb any kwargs dispatcher passes (e.g. payload=...)
    if not sig.parameters:

        @functools.wraps(fn)
        async def no_param_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await fn()

        return no_param_wrapper

    # Has parameters but no 'payload'
    if payload_param is None:
        raise TypeError(
            f"Task '{fn.__name__}' has parameters but no 'payload' parameter. "
            "Declare a single 'payload: <BaseModel subclass>' parameter or remove all parameters."
        )

    annotation = payload_param.annotation
    if not (inspect.isclass(annotation) and issubclass(annotation, BaseModel)):
        raise TypeError(
            f"Task '{fn.__name__}' has 'payload' parameter but its annotation ({annotation}) "
            "is not a Pydantic BaseModel subclass."
        )

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        raw = kwargs.get("payload", {})
        if not isinstance(raw, annotation):
            kwargs["payload"] = annotation.model_validate(raw)
        return await fn(*args, **kwargs)

    return wrapper


def task(name: str | None = None) -> Callable:
    """Register a function as a dispatchable task.

    Usage:
        @task()
        async def my_task(payload: MyPayload): ...

        @task(name="custom.name")
        async def my_task(payload: MyPayload): ...
    """

    def decorator(fn: Callable) -> Callable:
        key = name if name is not None else fn.__name__
        if key in _registry:
            raise ValueError(f"Task '{key}' is already registered.")
        wrapped = _wrap_with_payload_adapter(fn)
        _registry[key] = wrapped
        return fn

    return decorator


def get(name: str) -> Callable:
    """Look up a registered task by name. Raises KeyError if not found."""
    if name not in _registry:
        raise KeyError(f"Task '{name}' is not registered. Available tasks: {list(_registry)}")
    return _registry[name]


def all_tasks() -> dict[str, Callable]:
    """Return a copy of the full registry."""
    return dict(_registry)


def autodiscover(packages: str | list[str] | None = None) -> None:
    """Import modules so that @task decorators are registered.

    Args:
        packages: A package name or list of package names to scan (e.g., "app.features.execution.tasks").
                  If None, defaults to the parent package of this registry module.

    Call this once at application startup (e.g. in lifespan):
        from app.features import tasks
        tasks.autodiscover()
        # or
        # tasks.autodiscover(["app.other_module.tasks", "plugins.custom_tasks"])
    """
    if packages is None:
        # Default behavior: scan the parent directory of this module
        package_dir = Path(__file__).parent.parent
        # "__package__" is typically 'app.features.execution.tasks.core' -> rsplit gives 'app.features.execution.tasks'
        package_name = __package__.rsplit(".", 1)[0] if __package__ else "app.features.execution.tasks"
        _import_submodules(str(package_dir), package_name)
    else:
        # Scan explicitly provided packages
        pkg_list = [packages] if isinstance(packages, str) else packages
        for pkg_name in pkg_list:
            try:
                module = importlib.import_module(pkg_name)
                # Ensure the module has a path (is a package, not just a single file)
                if hasattr(module, "__path__"):
                    for path in module.__path__:
                        _import_submodules(path, pkg_name)
            except ImportError as e:
                raise ImportError(f"Failed to autodiscover tasks in package '{pkg_name}'") from e


def _import_submodules(package_dir: str, package_name: str) -> None:
    """Helper function to iterate and import submodules in a given directory."""
    for module_info in pkgutil.iter_modules([package_dir]):
        importlib.import_module(f"{package_name}.{module_info.name}")
