"""Higher level publishing utilities for pipeline outputs."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ModerationRequest,
    ModerationStatus,
    WorkspaceTelegramChannel,
)
from app.observability.alerts import alerting_client
from app.observability.logging import get_logger
from app.services.moderation import (
    moderation_request_to_dict,
    notify_moderation_event,
    serialize_flags,
)
from app.services.telegram import (
    TelegramPublisher,
    TelegramPublishingError,
    get_telegram_publisher,
)

logger = get_logger("services.publishing")

_FLAGGED_KEYWORDS: tuple[str, ...] = (
    "breach",
    "policy",
    "unsafe",
    "violence",
    "gambling",
    "explicit",
    "classified",
    "malware",
)
_HIGH_RISK_PHRASES: tuple[str, ...] = (
    "requires review",
    "human review",
    "do not publish",
    "sensitive content",
)
_MAX_MESSAGE_LENGTH = 4000


@dataclass(slots=True)
class ClassificationOutcome:
    """Encapsulates AI moderation attributes for a processed article."""

    score: float
    summary: str
    flags: list[str] = field(default_factory=list)
    requires_moderation: bool = False

    def to_payload(self) -> dict[str, object]:
        return {
            "score": self.score,
            "summary": self.summary,
            "flags": list(self.flags),
            "requires_moderation": self.requires_moderation,
        }


def classify_article(title: str, summary: str, body: str) -> ClassificationOutcome:
    """Apply a heuristic classifier to determine moderation needs."""

    text = f"{title} {summary} {body}".lower()
    matched_flags = sorted({keyword for keyword in _FLAGGED_KEYWORDS if keyword in text})
    score = 0.25 + 0.1 * len(matched_flags)

    if any(phrase in text for phrase in _HIGH_RISK_PHRASES):
        score = max(score, 0.85)
    if "unsafe" in text or "violence" in text:
        score = max(score, 0.8)

    requires_moderation = score >= 0.7 or bool(matched_flags)
    message = (
        "Flagged for review: " + ", ".join(matched_flags)
        if matched_flags
        else "Content auto-approved by heuristic"
    )
    if requires_moderation and not matched_flags:
        message = "Requires human review due to high-risk phrasing"

    return ClassificationOutcome(
        score=round(min(score, 1.0), 2),
        summary=message,
        flags=matched_flags,
        requires_moderation=requires_moderation,
    )


def get_active_telegram_channels(session: Session, workspace: str) -> list[WorkspaceTelegramChannel]:
    """Return all active telegram channels for the workspace."""

    result = session.execute(
        select(WorkspaceTelegramChannel).where(
            WorkspaceTelegramChannel.workspace == workspace,
            WorkspaceTelegramChannel.is_active.is_(True),
        )
    )
    channels = result.scalars().all()
    return list(channels)


def queue_moderation_request(
    session: Session,
    workspace: str,
    reference: str,
    title: str,
    excerpt: str | None,
    outcome: ClassificationOutcome,
) -> ModerationRequest | None:
    """Persist a moderation request if one does not already exist."""

    existing = session.execute(
        select(ModerationRequest).where(
            ModerationRequest.workspace == workspace,
            ModerationRequest.reference == reference,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None

    request = ModerationRequest(
        workspace=workspace,
        reference=reference,
        content_title=title,
        content_excerpt=excerpt,
        status=ModerationStatus.PENDING,
        ai_score=outcome.score,
        ai_summary=outcome.summary,
        ai_flags=serialize_flags(outcome.flags),
    )
    session.add(request)
    session.flush()
    session.refresh(request)

    logger.info(
        "queued moderation request",
        extra={"workspace": workspace, "reference": reference},
    )
    notify_moderation_event(
        {
            "type": "moderation.created",
            "request": moderation_request_to_dict(request),
        }
    )
    alerting_client.notify_failure(
        workspace,
        f"content queued for moderation: {reference}",
        severity="warning",
    )
    return request


def build_telegram_message(
    title: str,
    summary: str,
    author: str | None = None,
) -> str:
    """Generate a human-friendly Telegram message payload."""

    sections: list[str] = []
    cleaned_title = title.strip()
    if cleaned_title:
        sections.append(cleaned_title)
    cleaned_summary = summary.strip()
    if cleaned_summary:
        if sections:
            sections.append("")
        sections.append(cleaned_summary)
    if author:
        author_clean = author.strip()
        if author_clean:
            sections.append("")
            sections.append(f"— {author_clean}")

    message = "\n".join(sections)
    if len(message) > _MAX_MESSAGE_LENGTH:
        message = message[: _MAX_MESSAGE_LENGTH - 3].rstrip() + "..."
    return message


def deliver_to_telegram(
    publisher: TelegramPublisher,
    chat_id: str,
    message: str,
) -> None:
    """Send a message to Telegram, raising on failure."""

    try:
        publisher.send_message(chat_id, message)
    except TelegramPublishingError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise TelegramPublishingError(str(exc)) from exc


def ensure_publisher() -> TelegramPublisher:
    """Return the configured Telegram publisher instance."""

    return get_telegram_publisher()


__all__ = [
    "ClassificationOutcome",
    "classify_article",
    "get_active_telegram_channels",
    "queue_moderation_request",
    "build_telegram_message",
    "deliver_to_telegram",
    "ensure_publisher",
]
