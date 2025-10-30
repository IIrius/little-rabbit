"""Backend application package."""

from importlib import import_module
from typing import Any

__all__ = ["models"]


def __getattr__(name: str) -> Any:  # pragma: no cover - simple lazy import
    if name == "models":
        module = import_module("app.models")
        globals()[name] = module
        return module
    raise AttributeError(f"module 'app' has no attribute {name!r}")
