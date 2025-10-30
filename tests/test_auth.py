from __future__ import annotations

from sqlalchemy import select

from app import models


async def test_register_creates_user_with_workspace(async_client, db_session) -> None:
    payload = {
        "email": "new-user@example.com",
        "password": "SecurePass123!",
        "full_name": "New User",
        "role": "operator",
        "workspaces": ["dev"],
    }

    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == payload["email"]
    assert body["user"]["default_workspace"] == "dev"
    assert body["user"]["workspaces"]

    user = db_session.execute(
        select(models.User).where(models.User.email == payload["email"])
    ).scalar_one()
    assert user.default_workspace == "dev"
    assert {membership.workspace for membership in user.workspaces} == {"dev"}


async def test_login_returns_token_pair(async_client, user_factory) -> None:
    user, password = user_factory(email="login@example.com")

    response = await async_client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == user.email
