"""Alerting stubs for pipeline events."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from app.observability.logging import get_logger

logger = get_logger("observability.alerts")


@dataclass
class AlertEvent:
    """Represents a pipeline alert notification."""

    workspace: str
    severity: str
    message: str
    timestamp: datetime


class AlertingClient:
    """Stubbed alerting client for integration with incident tooling."""

    def __init__(self) -> None:
        self.events: List[AlertEvent] = []

    def notify_failure(
        self, workspace: str, message: str, severity: str = "critical"
    ) -> AlertEvent:
        event = AlertEvent(
            workspace=workspace,
            severity=severity,
            message=message,
            timestamp=datetime.now(timezone.utc),
        )
        self.events.append(event)
        logger.error(
            "pipeline failure alert",
            extra={
                "workspace": workspace,
                "severity": severity,
                "alert_message": message,
            },
        )
        return event

    def notify_success(self, workspace: str, published: int) -> AlertEvent:
        message = f"pipeline published {published} articles"
        event = AlertEvent(
            workspace=workspace,
            severity="info",
            message=message,
            timestamp=datetime.now(timezone.utc),
        )
        self.events.append(event)
        logger.info(
            "pipeline success notification",
            extra={"workspace": workspace, "published": published},
        )
        return event

    def reset(self) -> None:
        """Clear stored events (useful for testing)."""

        self.events.clear()


alerting_client = AlertingClient()


__all__ = ["AlertEvent", "AlertingClient", "alerting_client"]
