"""Tests for moderation console API and UI."""
from __future__ import annotations

from collections.abc import Iterable

from app import models
from app.services.moderation import serialize_flags


def _create_request(
    session,
    *,
    workspace: str = "alpha",
    reference: str = "article-1",
    title: str = "Breaking story",
    excerpt: str = "Key details to review",
    status: models.ModerationStatus = models.ModerationStatus.PENDING,
    ai_score: float = 0.78,
    ai_summary: str = "Potential policy breach detected",
    ai_flags: Iterable[str] = ("policy", "language"),
) -> models.ModerationRequest:
    request = models.ModerationRequest(
        workspace=workspace,
        reference=reference,
        content_title=title,
        content_excerpt=excerpt,
        status=status,
        ai_score=ai_score,
        ai_summary=ai_summary,
        ai_flags=serialize_flags(ai_flags),
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    session.expunge(request)
    return request


def test_moderation_queue_returns_pending_requests(client, db_session) -> None:
    pending = _create_request(db_session, reference="story-a")
    _create_request(
        db_session,
        reference="story-b",
        status=models.ModerationStatus.APPROVED,
    )

    response = client.get("/api/moderation/queue")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == pending.id
    assert body[0]["status"] == models.ModerationStatus.PENDING.value
    assert body[0]["ai_analysis"]["flags"] == ["policy", "language"]


def test_moderation_decision_updates_status_and_history(client, db_session) -> None:
    request = _create_request(db_session, reference="story-c")

    with client.websocket_connect("/api/moderation/notifications") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "moderation.connected"

        response = client.post(
            f"/api/moderation/requests/{request.id}/decision",
            json={"decision": "approved", "actor": "alice", "reason": "Looks good"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"] == models.ModerationStatus.APPROVED.value

        event = websocket.receive_json()
        assert event["type"] == "moderation.decision"
        assert event["decision"]["decision"] == models.ModerationStatus.APPROVED.value
        assert event["request"]["status"] == models.ModerationStatus.APPROVED.value

    stored = db_session.get(models.ModerationRequest, request.id)
    assert stored is not None
    assert stored.status == models.ModerationStatus.APPROVED

    history = client.get("/api/moderation/history", params={"status": "approved"})
    assert history.status_code == 200
    history_items = history.json()
    assert any(item["request_id"] == request.id for item in history_items)


def test_moderation_bulk_decision_updates_multiple_requests(client, db_session) -> None:
    first = _create_request(db_session, reference="bulk-a")
    second = _create_request(db_session, reference="bulk-b")
    third = _create_request(db_session, reference="bulk-c")

    response = client.post(
        "/api/moderation/requests/bulk-decision",
        json={
            "decision": "rejected",
            "actor": "bulk-bot",
            "reason": "Matched policy filter",
            "request_ids": [first.id, second.id],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert len(result) == 2
    assert {entry["request_id"] for entry in result} == {first.id, second.id}

    first_refreshed = db_session.get(models.ModerationRequest, first.id)
    second_refreshed = db_session.get(models.ModerationRequest, second.id)
    third_refreshed = db_session.get(models.ModerationRequest, third.id)

    assert first_refreshed.status == models.ModerationStatus.REJECTED
    assert second_refreshed.status == models.ModerationStatus.REJECTED
    assert third_refreshed.status == models.ModerationStatus.PENDING


def test_moderation_history_filters_workspace_and_actor(client, db_session) -> None:
    alpha_pending = _create_request(db_session, workspace="alpha", reference="wf-1")
    beta_pending = _create_request(db_session, workspace="beta", reference="wf-2")

    client.post(
        f"/api/moderation/requests/{alpha_pending.id}/decision",
        json={"decision": "approved", "actor": "coach", "reason": "Policy compliant"},
    )
    client.post(
        f"/api/moderation/requests/{beta_pending.id}/decision",
        json={"decision": "rejected", "actor": "reviewer", "reason": "Unsafe"},
    )

    response = client.get(
        "/api/moderation/history",
        params={"workspace": "alpha", "actor": "coach", "status": "approved"},
    )

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["decision"] == models.ModerationStatus.APPROVED.value
    assert items[0]["request_id"] == alpha_pending.id


def test_moderation_console_template_renders(client) -> None:
    response = client.get("/moderation")

    assert response.status_code == 200
    body = response.text
    assert "Moderation Console" in body
    assert "data-testid=\"moderation-console\"" in body
    assert "/api/moderation/queue" in body
    assert "id=\"history-panel\"" in body
