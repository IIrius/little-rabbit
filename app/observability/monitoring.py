"""Monitoring utilities for Grafana/Prometheus integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict

from app.observability.logging import get_logger

logger = get_logger("observability.monitoring")


@dataclass(frozen=True)
class DashboardStatus:
    """Represents the status of a workspace monitoring dashboard."""

    workspace: str
    datasource: str
    ensured_at: datetime


DASHBOARD_REGISTRY: Dict[str, DashboardStatus] = {}


def ensure_dashboard(workspace: str, datasource: str = "prometheus") -> DashboardStatus:
    """Ensure a monitoring dashboard exists for the given workspace."""

    status = DashboardStatus(
        workspace=workspace,
        datasource=datasource,
        ensured_at=datetime.now(timezone.utc),
    )
    DASHBOARD_REGISTRY[workspace] = status
    logger.info(
        "ensured monitoring dashboard",
        extra={"workspace": workspace, "datasource": datasource},
    )
    return status


__all__ = ["DashboardStatus", "DASHBOARD_REGISTRY", "ensure_dashboard"]
