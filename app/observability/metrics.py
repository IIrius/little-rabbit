"""Prometheus metrics for pipeline observability."""
from __future__ import annotations

import time

from prometheus_client import Counter, Gauge, Histogram

PIPELINE_RUN_COUNTER = Counter(
    "pipeline_runs_total",
    "Total number of pipeline executions by workspace and outcome.",
    labelnames=("workspace", "status"),
)
PIPELINE_PUBLISHED_COUNTER = Counter(
    "pipeline_published_articles_total",
    "Number of articles published by the pipeline per workspace.",
    labelnames=("workspace",),
)
PIPELINE_DURATION = Histogram(
    "pipeline_run_duration_seconds",
    "Duration of pipeline executions in seconds.",
    labelnames=("workspace",),
)
PIPELINE_LAST_RUN = Gauge(
    "pipeline_last_run_timestamp",
    "Unix timestamp of the last pipeline execution per workspace.",
    labelnames=("workspace",),
)


def record_pipeline_success(workspace: str, duration: float, published: int) -> None:
    """Record metrics for a successful pipeline execution."""

    PIPELINE_RUN_COUNTER.labels(workspace=workspace, status="success").inc()
    PIPELINE_PUBLISHED_COUNTER.labels(workspace=workspace).inc(published)
    PIPELINE_DURATION.labels(workspace=workspace).observe(duration)
    PIPELINE_LAST_RUN.labels(workspace=workspace).set(time.time())


def record_pipeline_failure(workspace: str, duration: float) -> None:
    """Record metrics for a failed pipeline execution."""

    PIPELINE_RUN_COUNTER.labels(workspace=workspace, status="failure").inc()
    PIPELINE_DURATION.labels(workspace=workspace).observe(duration)
    PIPELINE_LAST_RUN.labels(workspace=workspace).set(time.time())


__all__ = [
    "PIPELINE_RUN_COUNTER",
    "PIPELINE_PUBLISHED_COUNTER",
    "PIPELINE_DURATION",
    "PIPELINE_LAST_RUN",
    "record_pipeline_failure",
    "record_pipeline_success",
]
