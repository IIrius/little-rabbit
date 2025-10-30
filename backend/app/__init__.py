from importlib import import_module

integrations = import_module("app.integrations")

__all__ = ["integrations"]
