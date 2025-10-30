"""In-memory deduplication helpers for processing pipeline stages."""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Dict, Set

from app.observability.logging import get_logger

logger = get_logger("services.memory")


class MemoryService:
    """Simple thread-safe store tracking content fingerprints per workspace."""

    def __init__(self) -> None:
        self._fingerprints: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.Lock()

    def has_seen(self, workspace: str, fingerprint: str) -> bool:
        """Return True if the fingerprint was observed for the workspace."""

        with self._lock:
            return fingerprint in self._fingerprints.get(workspace, set())

    def remember(self, workspace: str, fingerprint: str) -> None:
        """Record the fingerprint for the workspace."""

        with self._lock:
            bucket = self._fingerprints.setdefault(workspace, set())
            bucket.add(fingerprint)
            logger.debug(
                "memory.remember",
                extra={"workspace": workspace, "fingerprint": fingerprint[:12]},
            )

    def reset(self) -> None:
        """Clear all tracked fingerprints."""

        with self._lock:
            self._fingerprints.clear()


_memory_service: MemoryService | None = None
_memory_lock = threading.Lock()


def get_memory_service() -> MemoryService:
    """Return the configured memory service instance."""

    global _memory_service
    with _memory_lock:
        if _memory_service is None:
            _memory_service = MemoryService()
        return _memory_service


def set_memory_service(service: MemoryService | None) -> None:
    """Override the memory service implementation (primarily for tests)."""

    global _memory_service
    with _memory_lock:
        _memory_service = service


__all__ = ["MemoryService", "get_memory_service", "set_memory_service"]
