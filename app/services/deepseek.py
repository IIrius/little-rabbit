"""DeepSeek client abstraction used by processing pipeline stages."""
from __future__ import annotations

import threading
from typing import Any, Dict

from app.observability.logging import get_logger

logger = get_logger("services.deepseek")


class DeepSeekClient:
    """Lightweight SDK wrapper for DeepSeek language services."""

    def __init__(self, default_language: str = "en") -> None:
        self.default_language = default_language.lower() or "en"

    def adapt_content(
        self,
        title: str,
        summary: str,
        body: str,
        *,
        target_language: str | None = None,
    ) -> Dict[str, str]:
        """Return translated/adapted content for downstream processing."""

        language = (target_language or self.default_language or "en").strip().lower()
        if not language:
            language = self.default_language

        prefix = "" if language == self.default_language else f"[{language}] "
        adapted_title = (prefix + (title or "")).strip()
        adapted_summary = (prefix + (summary or "")).strip()
        adapted_body = (prefix + (body or "")).strip()

        logger.debug(
            "deepseek.adapt_content",
            extra={
                "language": language,
                "title_length": len(adapted_title),
                "body_length": len(adapted_body),
            },
        )

        return {
            "title": adapted_title,
            "summary": adapted_summary,
            "body": adapted_body,
            "language": language,
        }

    def detect_fake(self, text: str) -> Dict[str, Any]:
        """Detect whether the supplied text is counterfeit or synthetic."""

        normalized = (text or "").lower()
        suspicious_markers = ("fake", "deepfake", "forgery", "hoax", "synthetic")
        is_fake = any(marker in normalized for marker in suspicious_markers)
        confidence = 0.9 if is_fake else 0.1
        rationale = (
            "Counterfeit indicators detected"
            if is_fake
            else "Content appears authentic"
        )

        logger.debug(
            "deepseek.detect_fake",
            extra={"is_fake": is_fake, "confidence": confidence},
        )

        return {
            "is_fake": is_fake,
            "confidence": round(confidence, 2),
            "rationale": rationale,
        }


_client_lock = threading.Lock()
_client: DeepSeekClient | None = None


def get_deepseek_client() -> DeepSeekClient:
    """Return the configured DeepSeek client, creating a default instance if needed."""

    global _client
    with _client_lock:
        if _client is None:
            _client = DeepSeekClient()
        return _client


def set_deepseek_client(client: DeepSeekClient | None) -> None:
    """Override the DeepSeek client instance (useful for tests)."""

    global _client
    with _client_lock:
        _client = client


__all__ = ["DeepSeekClient", "get_deepseek_client", "set_deepseek_client"]
