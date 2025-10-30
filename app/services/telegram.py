"""Telegram publishing utilities."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx

from app.config import get_settings
from app.observability.logging import get_logger

logger = get_logger("services.telegram")


class TelegramPublishingError(RuntimeError):
    """Raised when a Telegram API call fails."""


@dataclass
class TelegramMessageResult:
    """Represents the outcome of a Telegram sendMessage call."""

    chat_id: str
    message_id: str | None
    status_code: int
    ok: bool
    description: str | None = None


class TelegramPublisher:
    """Simple Telegram Bot API client for publishing messages."""

    def __init__(
        self,
        *,
        bot_token: str | None,
        base_url: str,
        timeout: float,
        client: httpx.Client | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)
        self._enabled = bool(bot_token)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def send_message(self, chat_id: str, text: str) -> TelegramMessageResult:
        if not self._enabled:
            raise TelegramPublishingError("Telegram publishing disabled")

        url = f"{self._base_url}/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }

        try:
            response = self._client.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
        except httpx.RequestError as exc:  # pragma: no cover - network failure
            logger.exception("telegram request failed", extra={"chat_id": chat_id})
            raise TelegramPublishingError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "telegram responded with error status",
                extra={"chat_id": chat_id, "status": exc.response.status_code},
            )
            raise TelegramPublishingError(str(exc)) from exc
        except ValueError as exc:  # pragma: no cover - invalid response payload
            logger.exception(
                "telegram response parsing failed", extra={"chat_id": chat_id}
            )
            raise TelegramPublishingError("invalid telegram response") from exc

        ok = bool(data.get("ok", response.status_code < 400))
        if not ok:
            description = str(data.get("description", "telegram error"))
            logger.warning(
                "telegram sendMessage reported failure",
                extra={"chat_id": chat_id, "description": description},
            )
            raise TelegramPublishingError(description)

        result = data.get("result", {})
        message_id: str | None = None
        if isinstance(result, dict):
            raw_id = result.get("message_id")
            if raw_id is not None:
                message_id = str(raw_id)

        description = str(data.get("description")) if data.get("description") else None
        logger.info(
            "telegram message sent",
            extra={"chat_id": chat_id, "message_id": message_id},
        )
        return TelegramMessageResult(
            chat_id=chat_id,
            message_id=message_id,
            status_code=response.status_code,
            ok=True,
            description=description,
        )


_TELEGRAM_PUBLISHER: TelegramPublisher | None = None
_publisher_lock = Lock()


def get_telegram_publisher() -> TelegramPublisher:
    global _TELEGRAM_PUBLISHER
    if _TELEGRAM_PUBLISHER is not None:
        return _TELEGRAM_PUBLISHER

    with _publisher_lock:
        if _TELEGRAM_PUBLISHER is None:
            settings = get_settings()
            _TELEGRAM_PUBLISHER = TelegramPublisher(
                bot_token=settings.telegram_bot_token,
                base_url=settings.telegram_api_base_url,
                timeout=settings.telegram_timeout_seconds,
            )
    return _TELEGRAM_PUBLISHER


def set_telegram_publisher(publisher: TelegramPublisher | None) -> None:
    global _TELEGRAM_PUBLISHER
    with _publisher_lock:
        _TELEGRAM_PUBLISHER = publisher


__all__ = [
    "TelegramPublisher",
    "TelegramPublishingError",
    "TelegramMessageResult",
    "get_telegram_publisher",
    "set_telegram_publisher",
]
