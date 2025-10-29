from __future__ import annotations

from fastapi.testclient import TestClient


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def register_user(
    client: TestClient,
    *,
    email: str,
    password: str,
    role: str = "operator",
    workspaces: list[str] | None = None,
) -> dict[str, object]:
    payload = {
        "email": email,
        "password": password,
        "full_name": "Test User",
        "role": role,
    }
    if workspaces is not None:
        payload["workspaces"] = workspaces
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def login_user(client: TestClient, *, email: str, password: str) -> dict[str, object]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_registration_and_login_flow(client: TestClient) -> None:
    email = "operator@example.com"
    password = "SecurePass123!"

    registration = register_user(client, email=email, password=password)
    assert registration["user"]["email"] == email
    assert registration["user"]["role"] == "operator"
    assert registration["user"]["workspaces"]

    login = login_user(client, email=email, password=password)
    assert login["access_token"]
    assert login["refresh_token"]
    assert login["user"]["email"] == email

    profile = client.get(
        "/api/auth/me",
        headers=auth_headers(login["access_token"]),
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == email


def test_refresh_token_rotation(client: TestClient) -> None:
    payload = register_user(
        client,
        email="refresh@example.com",
        password="RefreshPass123!",
        workspaces=["dev"],
    )

    first_refresh = payload["refresh_token"]
    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["refresh_token"] != first_refresh

    # Using the revoked token again should fail
    invalid = client.post(
        "/api/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert invalid.status_code == 401


def test_admin_guard_requires_role(client: TestClient) -> None:
    operator = register_user(
        client,
        email="guard-operator@example.com",
        password="GuardPass123!",
        role="operator",
    )
    guard = client.get(
        "/api/auth/guarded/admin",
        headers=auth_headers(operator["access_token"]),
    )
    assert guard.status_code == 403

    admin = register_user(
        client,
        email="admin@example.com",
        password="AdminPass123!",
        role="admin",
    )
    allowed = client.get(
        "/api/auth/guarded/admin",
        headers=auth_headers(admin["access_token"]),
    )
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "ok"


def test_password_reset_cycle(client: TestClient) -> None:
    email = "reset@example.com"
    original_password = "Original123!"
    new_password = "Updated123!"
    register_user(client, email=email, password=original_password)

    request = client.post(
        "/api/auth/password-reset/request",
        json={"email": email},
    )
    assert request.status_code == 200
    token = request.json()["reset_token"]
    assert token

    confirm = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "new_password": new_password},
    )
    assert confirm.status_code == 200

    login = login_user(client, email=email, password=new_password)
    assert login["user"]["email"] == email


def test_workspace_selection_updates_default(client: TestClient) -> None:
    payload = register_user(
        client,
        email="workspace@example.com",
        password="Workspace123!",
        workspaces=["dev", "staging"],
    )
    access_token = payload["access_token"]

    selection = client.post(
        "/api/auth/workspaces/select",
        headers=auth_headers(access_token),
        json={"workspace": "staging"},
    )
    assert selection.status_code == 200
    body = selection.json()
    assert body["default_workspace"] == "staging"


def test_available_workspaces_endpoint(client: TestClient) -> None:
    response = client.get("/api/auth/available-workspaces")
    assert response.status_code == 200
    workspaces = response.json()["workspaces"]
    assert "dev" in workspaces


def test_auth_portal_template(client: TestClient) -> None:
    response = client.get("/auth")
    assert response.status_code == 200
    html = response.text
    assert "id=\"login-form\"" in html
    assert "Register" in html
    assert "Reset token" in html


def test_registration_rejects_unknown_workspace(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "email": "unknown@example.com",
            "password": "UnknownPass123!",
            "role": "operator",
            "workspaces": ["unknown"],
        },
    )
    assert response.status_code == 422


def test_registration_duplicate_email(client: TestClient) -> None:
    register_user(
        client,
        email="duplicate@example.com",
        password="Duplicate123!",
    )
    response = client.post(
        "/api/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "Duplicate123!",
            "role": "operator",
        },
    )
    assert response.status_code == 409
