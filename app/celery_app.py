"""Celery application configuration for pipeline orchestration."""
from __future__ import annotations

from datetime import timedelta

from celery import Celery

from app.config import get_settings
from app.pipeline.config import load_workspace_configs

settings = get_settings()

celery_app = Celery("app")
celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_default_queue="pipelines",
    task_default_exchange="pipelines",
    task_default_routing_key="pipelines",
    beat_schedule={},
)

beat_entries = {}
for workspace, config in load_workspace_configs().items():
    if not config.enabled:
        continue
    beat_entries[f"pipeline::{workspace}"] = {
        "task": "app.pipeline.tasks.run_workspace_pipeline",
        "schedule": timedelta(seconds=config.schedule_seconds),
        "args": (workspace,),
    }

celery_app.conf.beat_schedule = beat_entries
celery_app.autodiscover_tasks(["app"])

if settings.app_env.lower() in {"development", "test"}:
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)


__all__ = ["celery_app"]
