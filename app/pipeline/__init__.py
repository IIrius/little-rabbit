"""Pipeline orchestration package."""

from __future__ import annotations

from typing import Any, Dict

__all__ = ["run_workspace_pipeline_sync", "trigger_workspace_pipeline"]


def run_workspace_pipeline_sync(workspace: str) -> Dict[str, Any]:
    from app.pipeline.runner import run_workspace_pipeline_sync as _run

    return _run(workspace)


def trigger_workspace_pipeline(workspace: str) -> str:
    from app.pipeline.runner import trigger_workspace_pipeline as _trigger

    return _trigger(workspace)
