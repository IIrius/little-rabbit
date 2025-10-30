from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend_app.integrations.telegram import client as telegram_client
from backend_app.integrations.telegram.client import TelegramError


@pytest.fixture
def fake_bot(monkeypatch: pytest.MonkeyPatch):
    instances: list["DummyBot"] = []

    class DummyBot:
        def __init__(self, token: str):
            self.token = token
            self.webhook_url: str | None = None
            self.deleted_webhook_with_drop: bool | None = None
            self.chat_requests: list[str] = []
            instances.append(self)

        async def set_webhook(self, url: str) -> None:
            self.webhook_url = url

        async def delete_webhook(self, drop_pending_updates: bool = False) -> None:
            self.deleted_webhook_with_drop = drop_pending_updates

        async def get_chat(self, chat_id: str):
            self.chat_requests.append(chat_id)
            if chat_id == "-999":
                raise TelegramError("failed to fetch chat")
            return SimpleNamespace(id=int(chat_id))

    DummyBot.instances = instances
    monkeypatch.setattr(telegram_client, "Bot", DummyBot, raising=False)
    yield DummyBot
    instances.clear()


def test_register_bot_with_webhook_sets_webhook(client, fake_bot) -> None:
    response = client.post(
        "/workspaces/webhook-co/telegram/bot",
        json={
            "token": "123:ABC",
            "strategy": "webhook",
            "webhook_url": "https://example.com/hook",
            "allowed_channel_ids": ["-10001", "-10002"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "workspace_id": "webhook-co",
        "strategy": "webhook",
        "webhook_url": "https://example.com/hook",
        "allowed_channel_ids": ["-10001", "-10002"],
        "bound_channel_id": None,
    }
    assert fake_bot.instances[0].webhook_url == "https://example.com/hook"
    assert fake_bot.instances[0].deleted_webhook_with_drop is None


def test_register_bot_with_polling_clears_webhook(client, fake_bot) -> None:
    response = client.post(
        "/workspaces/polling-co/telegram/bot",
        json={
            "token": "321:CBA",
            "strategy": "polling",
            "allowed_channel_ids": [],
        },
    )

    assert response.status_code == 200
    assert fake_bot.instances[0].webhook_url is None
    assert fake_bot.instances[0].deleted_webhook_with_drop is True


def test_bind_channel_success(client, fake_bot) -> None:
    register = client.post(
        "/workspaces/globex/telegram/bot",
        json={
            "token": "999:XYZ",
            "strategy": "polling",
            "allowed_channel_ids": ["-12345"],
        },
    )
    assert register.status_code == 200

    response = client.post(
        "/workspaces/globex/telegram/channel",
        json={"channel_id": "-12345"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["bound_channel_id"] == "-12345"
    assert fake_bot.instances[-1].chat_requests == ["-12345"]


def test_bind_channel_permission_denied(client, fake_bot) -> None:
    register = client.post(
        "/workspaces/initech/telegram/bot",
        json={
            "token": "777:XYZ",
            "strategy": "polling",
            "allowed_channel_ids": ["-500"],
        },
    )
    assert register.status_code == 200

    response = client.post(
        "/workspaces/initech/telegram/channel",
        json={"channel_id": "-9999"},
    )

    assert response.status_code == 403
    assert "cannot bind" in response.json()["detail"]


def test_bind_channel_requires_registration(client, fake_bot) -> None:
    response = client.post(
        "/workspaces/unregistered/telegram/channel",
        json={"channel_id": "-1"},
    )

    assert response.status_code == 404
    assert "No Telegram bot registered" in response.json()["detail"]


def test_bind_channel_handles_telegram_errors(client, fake_bot) -> None:
    register = client.post(
        "/workspaces/failure/telegram/bot",
        json={
            "token": "404:XYZ",
            "strategy": "polling",
            "allowed_channel_ids": ["-999"],
        },
    )
    assert register.status_code == 200

    response = client.post(
        "/workspaces/failure/telegram/channel",
        json={"channel_id": "-999"},
    )

    assert response.status_code == 400
    assert "Failed to bind" in response.json()["detail"]


def test_get_bot_returns_configuration(client, fake_bot) -> None:
    client.post(
        "/workspaces/status/telegram/bot",
        json={
            "token": "567:QWE",
            "strategy": "webhook",
            "webhook_url": "https://example.com/status",
            "allowed_channel_ids": ["-111"],
        },
    )

    response = client.get("/workspaces/status/telegram/bot")

    assert response.status_code == 200
    assert response.json() == {
        "workspace_id": "status",
        "strategy": "webhook",
        "webhook_url": "https://example.com/status",
        "allowed_channel_ids": ["-111"],
        "bound_channel_id": None,
    }
