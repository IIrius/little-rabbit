"""Rate limiting utilities."""
from __future__ import annotations

from threading import Lock

from cachetools import TTLCache


class RateLimiter:
    """Simple in-memory rate limiter using a fixed window strategy."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be greater than zero")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._requests: TTLCache[str, int] = TTLCache(
            maxsize=10_000, ttl=window_seconds
        )

    def is_allowed(self, identifier: str | None) -> bool:
        """Return True if the identifier is within the rate limit window."""

        key = identifier or "anonymous"
        with self._lock:
            current = self._requests.get(key, 0)
            if current >= self.max_requests:
                return False

            self._requests[key] = current + 1
            return True

    def remaining(self, identifier: str | None) -> int:
        """Return the number of requests remaining in the current window."""

        key = identifier or "anonymous"
        with self._lock:
            current = self._requests.get(key, 0)
            remaining = self.max_requests - current
            return remaining if remaining >= 0 else 0

    def reset(self, identifier: str | None = None) -> None:
        """Reset counters for an identifier or the entire limiter."""

        with self._lock:
            if identifier is None:
                self._requests.clear()
            else:
                self._requests.pop(identifier or "anonymous", None)
