"""Input sanitization helpers."""
from __future__ import annotations

from typing import Any

import bleach

_ALLOWED_TAGS: tuple[str, ...] = ()
_ALLOWED_ATTRIBUTES: dict[str, tuple[str, ...]] = {}
_ALLOWED_PROTOCOLS: tuple[str, ...] = ("http", "https", "mailto")


def sanitize_text(value: str | None) -> str | None:
    """Sanitize a potentially unsafe text payload.

    The sanitization strips HTML tags and JavaScript protocols while preserving
    legitimate text content. Whitespace is normalized to reduce injection vectors.
    """

    if value is None:
        return None

    cleaned = bleach.clean(
        value,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
    return cleaned.strip()


def sanitize_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a sanitized shallow copy of a mapping object."""

    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_text(value)
        else:
            sanitized[key] = value
    return sanitized
