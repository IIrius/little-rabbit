"""Convenience helpers for executing pipeline workflows."""
from __future__ import annotations

from typing import Any, Dict

from app.pipeline.tasks import run_workspace_pipeline


def run_workspace_pipeline_sync(workspace: str) -> Dict[str, Any]:
    """Execute the pipeline synchronously (useful for tests)."""

    result = run_workspace_pipeline.apply(args=(workspace,))
    if result.failed():  # pragma: no cover - surfaced in failing tests
        raise result.result
    return result.get()


def trigger_workspace_pipeline(workspace: str) -> str:
    """Schedule the pipeline to run asynchronously and return the task id."""

    async_result = run_workspace_pipeline.delay(workspace)
    return async_result.id


__all__ = ["run_workspace_pipeline_sync", "trigger_workspace_pipeline"]
