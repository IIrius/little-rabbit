from __future__ import annotations

from typing import Any, Optional, Set

try:  # pragma: no cover - dependency resolution is environment specific
    from telegram import Bot as TelegramBot  # type: ignore[attr-defined]
    from telegram.error import TelegramError  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - exercised in unit tests via patching
    TelegramBot = None  # type: ignore[assignment]
    TelegramError = Exception

from .exceptions import (
    TelegramChannelBindingError,
    TelegramClientError,
    TelegramConfigurationError,
    TelegramPermissionError,
    TelegramWorkspaceNotRegisteredError,
)
from .models import DeliveryStrategy, WorkspaceTelegramConfig
from .storage import WorkspaceTelegramStore

Bot = TelegramBot  # Backwards compatibility alias used by tests


def _create_bot(token: str) -> Any:
    if Bot is None:
        raise TelegramConfigurationError(
            "python-telegram-bot dependency is required but not installed."
        )
    return Bot(token)  # type: ignore[return-value]


class TelegramClient:
    def __init__(self, store: WorkspaceTelegramStore) -> None:
        self._store = store

    async def register_bot(
        self,
        *,
        workspace_id: str,
        token: str,
        strategy: DeliveryStrategy,
        webhook_url: Optional[str] = None,
        allowed_channel_ids: Optional[Set[str]] = None,
    ) -> WorkspaceTelegramConfig:
        if strategy is DeliveryStrategy.WEBHOOK and not webhook_url:
            raise TelegramConfigurationError(
                "Webhook URL must be provided when using the webhook strategy."
            )

        config = WorkspaceTelegramConfig(
            workspace_id=workspace_id,
            token=token,
            strategy=strategy,
            webhook_url=webhook_url,
            allowed_channel_ids=set(allowed_channel_ids or set()),
            bound_channel_id=None,
        )

        try:
            await self._apply_delivery_strategy(config)
        except TelegramError as exc:
            raise TelegramClientError(
                "Failed to apply Telegram delivery strategy"
            ) from exc

        self._store.save(config)
        return config

    async def bind_channel(
        self, *, workspace_id: str, channel_id: str
    ) -> WorkspaceTelegramConfig:
        config = self._store.get(workspace_id)
        if config is None:
            raise TelegramWorkspaceNotRegisteredError(
                f"No Telegram bot registered for workspace '{workspace_id}'."
            )

        if not config.is_channel_allowed(channel_id):
            raise TelegramPermissionError(
                f"Workspace '{workspace_id}' cannot bind to channel '{channel_id}'."
            )

        bot = _create_bot(config.token)
        try:
            chat = await bot.get_chat(chat_id=channel_id)
        except TelegramError as exc:
            raise TelegramChannelBindingError(
                f"Failed to bind workspace '{workspace_id}' to channel '{channel_id}'."
            ) from exc

        config.bound_channel_id = str(chat.id)
        self._store.save(config)
        return config

    def get_config(self, workspace_id: str) -> WorkspaceTelegramConfig:
        config = self._store.get(workspace_id)
        if config is None:
            raise TelegramWorkspaceNotRegisteredError(
                f"No Telegram bot registered for workspace '{workspace_id}'."
            )
        return config

    async def _apply_delivery_strategy(self, config: WorkspaceTelegramConfig) -> None:
        bot = _create_bot(config.token)

        if config.strategy is DeliveryStrategy.WEBHOOK:
            assert config.webhook_url is not None
            await bot.set_webhook(url=config.webhook_url)
            return

        await bot.delete_webhook(drop_pending_updates=True)
