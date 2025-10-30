"""End-to-end integration tests for the news ingestion pipeline."""
from __future__ import annotations

import json

from sqlalchemy import select

from app.config import get_settings
from app.models import (
    ModerationRequest,
    ModerationStatus,
    NewsArticle,
    WorkspaceTelegramChannel,
)
from app.observability.alerts import alerting_client
from app.observability.monitoring import DASHBOARD_REGISTRY
from app.pipeline.config import load_workspace_configs
from app.pipeline.runner import run_workspace_pipeline_sync
from app.services import telegram as telegram_service
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
    assert b'pipeline_runs_total{status="success",workspace="dev"}' in metrics_blob
    assert b'pipeline_published_articles_total{workspace="dev"}' in metrics_blob

    assert "dev" in DASHBOARD_REGISTRY

    failure_events = [
        event for event in alerting_client.events if event.severity == "critical"
    ]
    assert not failure_events


def test_pipeline_telegram_publishing_and_moderation(
    monkeypatch, db_session, client
) -> None:
    alerting_client.reset()
    load_workspace_configs.cache_clear()

    monkeypatch.setenv(
        "WORKSPACE_PIPELINES_JSON",
        json.dumps(
            {
                "beta": {
                    "workspace": "beta",
                    "enabled": True,
                    "schedule_seconds": 120,
                    "retry_attempts": 1,
                    "retry_delay_seconds": 1,
                    "sources": [
                        {
                            "title": "Safe launch update",
                            "body": "New features shipping soon and suitable for broadcast.",
                            "author": "automation-bot",
                        },
                        {
                            "title": "Policy breach reported",
                            "body": (
                                "Unsafe content triggers a policy breach and requires human review. "
                                "Mark for moderation."
                            ),
                            "author": "watchdog",
                        },
                    ],
                }
            }
        ),
    )
    load_workspace_configs.cache_clear()
    get_settings.cache_clear()

    channel_primary = WorkspaceTelegramChannel(
        workspace="beta",
        name="Alerts",
        chat_id="@beta_alerts",
        is_active=True,
    )
    channel_secondary = WorkspaceTelegramChannel(
        workspace="beta",
        name="Updates",
        chat_id="123456789",
        is_active=True,
    )
    db_session.add_all([channel_primary, channel_secondary])
    db_session.commit()

    class RecordingPublisher:
        def __init__(self) -> None:
            self.enabled = True
            self.messages: list[tuple[str, str]] = []

        def send_message(self, chat_id: str, text: str) -> None:
            self.messages.append((chat_id, text))

    publisher = RecordingPublisher()
    telegram_service.set_telegram_publisher(publisher)

    result = run_workspace_pipeline_sync("beta")

    assert result["workspace"] == "beta"
    assert result["published"] == 2
    assert result["delivered"] == 2
    assert result["moderation"] == 1

    assert len(publisher.messages) == 2
    delivered_chats = {chat_id for chat_id, _ in publisher.messages}
    assert delivered_chats == {channel_primary.chat_id, channel_secondary.chat_id}
    assert all("Safe launch update" in message for _, message in publisher.messages)

    requests = (
        db_session.execute(
            select(ModerationRequest).where(ModerationRequest.workspace == "beta")
        )
        .scalars()
        .all()
    )
    assert len(requests) == 1
    moderation_request = requests[0]
    assert moderation_request.status == ModerationStatus.PENDING
    assert "policy" in moderation_request.ai_summary.lower()

    queue_response = client.get("/api/moderation/queue")
    assert queue_response.status_code == 200
    queue_items = queue_response.json()
    flagged = [item for item in queue_items if item["workspace"] == "beta"]
    assert len(flagged) == 1
    assert flagged[0]["ai_analysis"]["flags"]

    warning_events = [
        event for event in alerting_client.events if event.severity == "warning"
    ]
    assert warning_events, "expected moderation warning notification"

    metrics_blob = generate_latest()
    assert b'pipeline_telegram_messages_total{workspace="beta"}' in metrics_blob
    assert b'pipeline_moderation_requests_total{workspace="beta"}' in metrics_blob

    telegram_service.set_telegram_publisher(None)
    alerting_client.reset()
    load_workspace_configs.cache_clear()
