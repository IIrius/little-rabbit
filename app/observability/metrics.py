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
PIPELINE_TELEGRAM_MESSAGES_COUNTER = Counter(
    "pipeline_telegram_messages_total",
    "Number of Telegram messages delivered by the pipeline per workspace.",
    labelnames=("workspace",),
)
PIPELINE_MODERATION_REQUESTS_COUNTER = Counter(
    "pipeline_moderation_requests_total",
    "Number of moderation requests created by the pipeline per workspace.",
    labelnames=("workspace",),
)
PIPELINE_DUPLICATE_COUNTER = Counter(
    "pipeline_duplicates_total",
    "Number of items skipped due to deduplication per workspace.",
    labelnames=("workspace",),
)
PIPELINE_REJECTED_COUNTER = Counter(
    "pipeline_rejected_items_total",
    "Number of items rejected by the pipeline per workspace.",
    labelnames=("workspace",),
)
PIPELINE_FAKE_DETECTIONS_COUNTER = Counter(
    "pipeline_fake_detections_total",
    "Number of fake content detections flagged by the pipeline per workspace.",
    labelnames=("workspace",),
)


def record_pipeline_success(
    workspace: str,
    duration: float,
    published: int,
    delivered: int = 0,
    moderated: int = 0,
    rejected: int = 0,
    duplicates: int = 0,
    fake_detected: int = 0,
) -> None:
    """Record metrics for a successful pipeline execution."""

    PIPELINE_RUN_COUNTER.labels(workspace=workspace, status="success").inc()
    PIPELINE_PUBLISHED_COUNTER.labels(workspace=workspace).inc(published)
    if delivered:
        PIPELINE_TELEGRAM_MESSAGES_COUNTER.labels(workspace=workspace).inc(delivered)
    if moderated:
        PIPELINE_MODERATION_REQUESTS_COUNTER.labels(workspace=workspace).inc(moderated)
    if duplicates:
        PIPELINE_DUPLICATE_COUNTER.labels(workspace=workspace).inc(duplicates)
    if rejected:
        PIPELINE_REJECTED_COUNTER.labels(workspace=workspace).inc(rejected)
    if fake_detected:
        PIPELINE_FAKE_DETECTIONS_COUNTER.labels(workspace=workspace).inc(fake_detected)
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
    "PIPELINE_TELEGRAM_MESSAGES_COUNTER",
    "PIPELINE_MODERATION_REQUESTS_COUNTER",
    "PIPELINE_DUPLICATE_COUNTER",
    "PIPELINE_REJECTED_COUNTER",
    "PIPELINE_FAKE_DETECTIONS_COUNTER",
    "record_pipeline_failure",
    "record_pipeline_success",
]
