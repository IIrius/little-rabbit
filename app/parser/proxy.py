"""Interfaces for SOCKS5 proxy management in parsers."""
from __future__ import annotations

from collections import deque
from typing import Protocol, Sequence


class Socks5ProxyManager(Protocol):
    """Abstract interface for acquiring and releasing SOCKS5 proxies."""

    def acquire(self) -> str | None:
        """Return the next proxy to use or ``None`` if none are available."""

    def release(self, proxy: str, success: bool) -> None:
        """Release a previously acquired proxy, optionally marking success."""


class RoundRobinSocks5ProxyManager:
    """Round-robin implementation of :class:`Socks5ProxyManager`."""

    def __init__(self, proxies: Sequence[str]) -> None:
        self._proxies = [proxy for proxy in proxies if proxy]
        self._rotation = deque(self._proxies)

    def acquire(self) -> str | None:
        if not self._rotation:
            return None
        proxy = self._rotation[0]
        self._rotation.rotate(-1)
        return proxy

    def release(self, proxy: str, success: bool) -> None:  # pragma: no cover - noop
        # The round-robin implementation does not currently recycle based on the
        # success flag, but the method is present to satisfy the interface and to
        # make future implementations drop-in compatible.
        return

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"RoundRobinSocks5ProxyManager(proxies={len(self._proxies)})"


__all__ = ["RoundRobinSocks5ProxyManager", "Socks5ProxyManager"]
