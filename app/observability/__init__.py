"""Observability utilities for metrics, logging, and alerting."""
from app.observability.alerts import alerting_client
from app.observability.logging import get_logger, setup_structured_logging
from app.observability.metrics import (
    PIPELINE_DURATION,
    PIPELINE_LAST_RUN,
    PIPELINE_PUBLISHED_COUNTER,
    PIPELINE_RUN_COUNTER,
    PIPELINE_TELEGRAM_MESSAGES_COUNTER,
    PIPELINE_MODERATION_REQUESTS_COUNTER,
    record_pipeline_failure,
    record_pipeline_success,
)
from app.observability.monitoring import DASHBOARD_REGISTRY, ensure_dashboard

__all__ = [
    "alerting_client",
    "ensure_dashboard",
    "DASHBOARD_REGISTRY",
    "get_logger",
    "setup_structured_logging",
    "PIPELINE_DURATION",
    "PIPELINE_LAST_RUN",
    "PIPELINE_PUBLISHED_COUNTER",
    "PIPELINE_RUN_COUNTER",
    "PIPELINE_TELEGRAM_MESSAGES_COUNTER",
    "PIPELINE_MODERATION_REQUESTS_COUNTER",
    "record_pipeline_failure",
    "record_pipeline_success",
]
