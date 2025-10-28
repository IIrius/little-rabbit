"""Security posture regression tests."""
from __future__ import annotations

from fastapi import status
from sqlalchemy import select

from app import models
from app.config import get_settings


def test_item_creation_sanitizes_and_encrypts(client, db_session) -> None:
    payload = {
        "name": "<script>alert(1)</script>Widget",
        "description": "<b>Important</b> description",
    }

    response = client.post("/api/items", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()

    assert body["name"] == "alert(1)Widget"
    assert body["description"] == "Important description"

    item = (
        db_session.execute(select(models.Item).where(models.Item.id == body["id"]))
        .scalar_one()
    )
    assert item.description != body["description"]


def test_rate_limiting_enforced(client) -> None:
    settings = get_settings()
    limit = settings.rate_limit_max_requests

    for _ in range(limit):
        healthy = client.get("/api/health")
        assert healthy.status_code == status.HTTP_200_OK

    response = client.get("/api/health")
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.json()["detail"] == "Rate limit exceeded"
