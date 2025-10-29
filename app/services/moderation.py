"""Moderation service utilities."""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Sequence

import anyio
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.models import ModerationDecision, ModerationRequest
from app.security.sanitization import sanitize_text


class ModerationNotifier:
    """In-memory broker for moderation WebSocket notifications."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        with self._lock:
            self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message)
        with self._lock:
            connections = list(self._connections)
        stale: list[WebSocket] = []
        for connection in connections:
            try:
                await connection.send_text(payload)
            except Exception:  # pragma: no cover - defensive cleanup
                stale.append(connection)
        if stale:
            with self._lock:
                for connection in stale:
                    self._connections.discard(connection)


moderation_notifier = ModerationNotifier()


def serialize_flags(flags: Sequence[str] | None) -> str | None:
    """Convert a flag collection into a storage-friendly string."""

    if not flags:
        return None
    cleaned: list[str] = []
    for flag in flags:
        sanitized = sanitize_text(str(flag)) if flag is not None else None
        if sanitized:
            cleaned.append(sanitized)
    if not cleaned:
        return None
    return " | ".join(cleaned)


def parse_flags(raw_flags: str | None) -> list[str]:
    """Parse a stored flag string into a sanitized list."""

    if raw_flags is None:
        return []
    parts = [sanitize_text(part) for part in raw_flags.split("|")]
    return [part for part in parts if part]


def moderation_request_to_dict(request: ModerationRequest) -> dict[str, Any]:
    """Serialize a moderation request for API responses."""

    return {
        "id": request.id,
        "workspace": request.workspace,
        "reference": request.reference,
        "status": request.status.value,
        "submitted_at": request.submitted_at,
        "content_title": request.content_title,
        "content_excerpt": request.content_excerpt,
        "ai_analysis": {
            "score": request.ai_score,
            "summary": request.ai_summary,
            "flags": parse_flags(request.ai_flags),
        },
    }


def moderation_decision_to_dict(decision: ModerationDecision) -> dict[str, Any]:
    """Serialize a moderation decision for API responses."""

    return {
        "id": decision.id,
        "request_id": decision.request_id,
        "decision": decision.decision.value,
        "decided_at": decision.decided_at,
        "decided_by": decision.decided_by,
        "reason": decision.reason,
    }


async def listen_for_client_messages(websocket: WebSocket) -> None:
    """Consume websocket messages until the client disconnects."""

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass


def notify_moderation_event(payload: dict[str, Any]) -> None:
    """Dispatch a moderation notification to all connected clients."""

    try:
        anyio.from_thread.run(moderation_notifier.broadcast, payload)
    except RuntimeError:
        # Already running inside the event loop; fall back to create_task.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover - defensive fallback
            asyncio.run(moderation_notifier.broadcast(payload))
        else:
            loop.create_task(moderation_notifier.broadcast(payload))
