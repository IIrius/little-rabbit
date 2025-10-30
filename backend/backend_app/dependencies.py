from __future__ import annotations

from backend_app.integrations.telegram.client import TelegramClient
from backend_app.integrations.telegram.storage import InMemoryWorkspaceTelegramStore

_telegram_store = InMemoryWorkspaceTelegramStore()
_telegram_client = TelegramClient(_telegram_store)


def get_telegram_client() -> TelegramClient:
    return _telegram_client
