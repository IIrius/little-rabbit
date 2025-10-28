"""Audit logging utilities."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

AUDIT_LOGGER_NAME = "app.audit"


def configure_audit_logger(log_path: str) -> logging.Logger:
    """Configure the audit logger with file rotation."""

    logger = logging.getLogger(AUDIT_LOGGER_NAME)
    if logger.handlers:
        return logger

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    handler = TimedRotatingFileHandler(
        path, when="midnight", backupCount=30, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False

    return logger


def get_audit_logger() -> logging.Logger:
    """Return the configured audit logger."""

    return logging.getLogger(AUDIT_LOGGER_NAME)


def record_audit_event(event: str, **details: Any) -> None:
    """Record a structured audit log entry."""

    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **details,
    }
    get_audit_logger().info(json.dumps(payload, sort_keys=True))
