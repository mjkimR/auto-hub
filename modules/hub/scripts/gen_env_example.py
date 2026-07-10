"""
Generates .env.example by introspecting all BaseSettings subclasses loaded in the app.

Usage (from modules/hub directory):
    uv run python scripts/gen_env_example.py
"""

import inspect
import os
import sys
import types as _types
import typing as _typing

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load all dependencies to trigger module-level imports
from app.features import tasks  # type: ignore
from app.main import create_app  # type: ignore  # noqa: F401
from pydantic_settings import BaseSettings

# Task modules are imported at app lifespan, not at import time, so their settings
# classes would otherwise be invisible to the subclass walk below.
tasks.autodiscover()

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.example")


def _all_subclasses(cls):
    result = []
    for sub in cls.__subclasses__():
        if not inspect.isabstract(sub):
            result.append(sub)
        result.extend(_all_subclasses(sub))
    return result


SKIP_MODULES = {
    "pydantic_settings",
    "pydantic",
}


def _should_include(cls) -> bool:
    module = cls.__module__ or ""
    return not any(module.startswith(skip) for skip in SKIP_MODULES)


settings_classes = [cls for cls in _all_subclasses(BaseSettings) if _should_include(cls)]


def _type_str(tp) -> str:
    if tp is type(None):
        return "None"
    origin = _typing.get_origin(tp)
    args = _typing.get_args(tp)
    _UnionType = getattr(_types, "UnionType", None)
    is_union = origin is _typing.Union or (_UnionType is not None and origin is _UnionType)
    if is_union:
        return " | ".join(_type_str(a) for a in args)
    if origin is not None and args:
        origin_name = getattr(origin, "__name__", str(origin))
        args_str = ", ".join(_type_str(a) for a in args)
        return f"{origin_name}[{args_str}]"
    return getattr(tp, "__name__", str(tp))


# Build .env.example content
lines: list[str] = []

for cls in settings_classes:
    env_prefix = (cls.model_config or {}).get("env_prefix", "")
    lines.append(f"# ── {cls.__name__} (module: {cls.__module__}) ──")

    for field_name, field_info in cls.model_fields.items():
        env_var = f"{env_prefix}{field_info.alias or field_name.upper()}"

        type_str = _type_str(field_info.annotation)
        description = field_info.description or ""
        default = field_info.default

        is_required = default is inspect.Parameter.empty or (
            hasattr(field_info, "is_required") and field_info.is_required()
        )
        has_default_factory = field_info.default_factory is not None
        has_default = not is_required or has_default_factory

        if type_str == "SecretStr":
            value_hint = "<secret>"
        elif has_default_factory or is_required or default is None:
            value_hint = ""
        else:
            value_hint = str(default)

        required_tag = "" if has_default else ", required"
        auto_tag = ", auto-generated" if has_default_factory else ""
        type_info = f"({type_str}{required_tag}{auto_tag})"
        comment_text = f"{description} {type_info}" if description else type_info

        # Use '##' for descriptions and '#' for disabled variables
        lines.append(f"## {comment_text}")

        env_line = f"{env_var}={value_hint}"
        lines.append(f"# {env_line}" if has_default else env_line)
        lines.append("")  # Add an empty line for separation

    lines.append("")

content = "\n".join(lines)

with open(OUTPUT_PATH, "w") as f:
    f.write(content)

print(f"✅  .env.example generated → {OUTPUT_PATH}")
print(f"   {len(settings_classes)} settings class(es) found: {[c.__name__ for c in settings_classes]}")
