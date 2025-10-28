"""Structured logging helpers used across the application."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

RESERVED_RECORD_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
}


class StructuredLogFormatter(logging.Formatter):
    """Formatter that renders log records as JSON for easier ingestion."""

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in RESERVED_RECORD_FIELDS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Ensure the application's loggers emit structured output."""

    logger = logging.getLogger("app")
    for handler in logger.handlers:
        if isinstance(handler.formatter, StructuredLogFormatter):
            return

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredLogFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger that is configured for structured output."""

    setup_structured_logging()
    return logging.getLogger(f"app.{name}")


__all__ = ["get_logger", "setup_structured_logging", "StructuredLogFormatter"]
