"""End-to-end integration tests for the news ingestion pipeline."""
from __future__ import annotations

from sqlalchemy import select

from app.models import NewsArticle
from app.observability.alerts import alerting_client
from app.observability.monitoring import DASHBOARD_REGISTRY
from app.pipeline.runner import run_workspace_pipeline_sync
from prometheus_client import generate_latest


def test_pipeline_publishes_sample_news(db_session) -> None:
    alerting_client.reset()

    result = run_workspace_pipeline_sync("dev")

    assert result["workspace"] == "dev"
    assert result["published"] >= 1

    articles = db_session.execute(select(NewsArticle)).scalars().all()
    assert articles, "expected at least one article to be published"

    article = articles[0]
    assert article.workspace == "dev"
    assert "pipeline" in article.title.lower()
    assert article.summary

    metrics_blob = generate_latest()
    assert b'pipeline_runs_total{workspace="dev",status="success"}' in metrics_blob
    assert b'pipeline_published_articles_total{workspace="dev"}' in metrics_blob

    assert "dev" in DASHBOARD_REGISTRY

    failure_events = [event for event in alerting_client.events if event.severity == "critical"]
    assert not failure_events
