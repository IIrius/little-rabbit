"""Celery tasks that orchestrate news ingestion pipelines."""
from __future__ import annotations

import time
from typing import Any, Dict, List
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import NewsArticle, WorkspaceTelegramChannel
from app.observability.alerts import alerting_client
from app.observability.logging import get_logger
from app.observability.metrics import (
    record_pipeline_failure,
    record_pipeline_success,
)
from app.observability.monitoring import ensure_dashboard
from app.pipeline.config import get_workspace_config
from app.security.sanitization import sanitize_text
from app.services.publishing import (
    ClassificationOutcome,
    build_telegram_message,
    classify_article,
    deliver_to_telegram,
    ensure_publisher,
    get_active_telegram_channels,
    queue_moderation_request,
)
from app.services.telegram import TelegramPublishingError

logger = get_logger("pipeline.tasks")


def _slugify(value: str) -> str:
    processed = [char.lower() if char.isalnum() else "-" for char in value.strip()]
    slug = "".join(processed)
    slug = "-".join(filter(None, slug.split("-")))
    if not slug:
        slug = f"article-{uuid4().hex}"
    return slug[:255]


def _outcome_from_payload(payload: dict[str, Any]) -> ClassificationOutcome:
    flags = payload.get("flags") or []
    normalized_flags = [str(flag) for flag in flags if flag is not None]
    return ClassificationOutcome(
        score=float(payload.get("score", 0.0)),
        summary=str(payload.get("summary", "")),
        flags=normalized_flags,
        requires_moderation=bool(payload.get("requires_moderation", False)),
    )


@celery_app.task(bind=True, name="app.pipeline.tasks.parse_news")
def parse_news(self, workspace: str) -> List[dict[str, Any]]:
    """Retrieve raw news payloads for the workspace."""

    config = get_workspace_config(workspace)
    if not config.enabled:
        logger.info("workspace pipeline disabled", extra={"workspace": workspace})
        return []

    payloads = [item.dict() for item in config.sources]
    logger.info(
        "parsed raw news payloads",
        extra={"workspace": workspace, "count": len(payloads)},
    )
    return payloads


@celery_app.task(bind=True, name="app.pipeline.tasks.process_news")
def process_news(
    self, workspace: str, raw_items: List[dict[str, Any]]
) -> List[dict[str, Any]]:
    """Clean and enrich raw payloads prior to publication."""

    processed: List[dict[str, Any]] = []

    for payload in raw_items:
        title = sanitize_text(payload.get("title", "")) or "Untitled article"
        body = sanitize_text(payload.get("body", "")) or ""
        author = sanitize_text(payload.get("author")) if payload.get("author") else None
        summary = sanitize_text(body[:280]) or title
        slug = _slugify(title)

        processed.append(
            {
                "workspace": workspace,
                "slug": slug,
                "title": title,
                "summary": summary,
                "body": body,
                "author": author,
            }
        )

    logger.info(
        "processed news payloads",
        extra={"workspace": workspace, "count": len(processed)},
    )
    return processed


@celery_app.task(bind=True, name="app.pipeline.tasks.classify_news")
def classify_news(
    self, workspace: str, processed_items: List[dict[str, Any]]
) -> List[dict[str, Any]]:
    """Classify processed articles to determine moderation requirements."""

    classified: List[dict[str, Any]] = []
    moderation_required = 0

    for item in processed_items:
        outcome = classify_article(item["title"], item["summary"], item["body"])
        payload = dict(item)
        payload["classification"] = outcome.to_payload()
        if outcome.requires_moderation:
            moderation_required += 1
        classified.append(payload)

    logger.info(
        "classified news items",
        extra={
            "workspace": workspace,
            "count": len(classified),
            "moderation_required": moderation_required,
        },
    )
    return classified


@celery_app.task(bind=True, name="app.pipeline.tasks.publish_news")
def publish_news(
    self, workspace: str, processed_items: List[dict[str, Any]]
) -> Dict[str, int]:
    """Persist processed payloads into the database."""

    session: Session = SessionLocal()
    published = 0

    try:
        for item in processed_items:
            slug = item["slug"]
            existing = session.execute(
                select(NewsArticle).where(
                    NewsArticle.workspace == workspace,
                    NewsArticle.slug == slug,
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue

            article = NewsArticle(
                workspace=workspace,
                slug=slug,
                title=item["title"],
                summary=item["summary"],
                body=item["body"],
                author=item.get("author"),
            )
            session.add(article)
            published += 1

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info(
        "published news items",
        extra={"workspace": workspace, "count": published},
    )
    return {"published": published}


@celery_app.task(bind=True, name="app.pipeline.tasks.publish_to_telegram")
def publish_to_telegram(
    self,
    workspace: str,
    classified_items: List[dict[str, Any]],
    retry_attempts: int = 3,
    retry_delay_seconds: int = 30,
) -> Dict[str, int]:
    """Deliver classified articles to Telegram channels and queue moderation."""

    session: Session = SessionLocal()
    delivered = 0
    moderated = 0
    failures: List[str] = []
    channels: List[WorkspaceTelegramChannel] = []
    publisher = ensure_publisher()
    publisher_enabled = publisher.enabled

    try:
        channels = get_active_telegram_channels(session, workspace)
        if not channels:
            logger.info(
                "no active telegram channels configured",
                extra={"workspace": workspace},
            )
        if not publisher_enabled:
            logger.info(
                "telegram publisher disabled; skipping message delivery",
                extra={"workspace": workspace},
            )

        for item in classified_items:
            classification_payload = item.get("classification") or {}
            outcome = _outcome_from_payload(classification_payload)
            if outcome.requires_moderation:
                created = queue_moderation_request(
                    session,
                    workspace=workspace,
                    reference=item["slug"],
                    title=item["title"],
                    excerpt=item.get("summary"),
                    outcome=outcome,
                )
                if created is not None:
                    moderated += 1
                continue

            if not channels or not publisher_enabled:
                continue

            message = build_telegram_message(
                item["title"], item["summary"], item.get("author")
            )
            for channel in channels:
                try:
                    deliver_to_telegram(publisher, channel.chat_id, message)
                except TelegramPublishingError as exc:
                    failure_message = f"{channel.chat_id}: {exc}"
                    failures.append(failure_message)
                    logger.warning(
                        "telegram delivery failed",
                        extra={
                            "workspace": workspace,
                            "slug": item["slug"],
                            "chat_id": channel.chat_id,
                        },
                    )
                    alerting_client.notify_failure(
                        workspace,
                        f"telegram delivery failed for {channel.chat_id}: {exc}",
                        severity="warning",
                    )
                else:
                    delivered += 1
                    logger.info(
                        "telegram message delivered",
                        extra={
                            "workspace": workspace,
                            "slug": item["slug"],
                            "chat_id": channel.chat_id,
                        },
                    )

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if failures:
        error_message = "; ".join(failures)
        if retry_attempts and self.request.retries < retry_attempts:
            raise self.retry(
                exc=TelegramPublishingError(error_message),
                countdown=retry_delay_seconds,
                max_retries=retry_attempts,
            )
        raise TelegramPublishingError(error_message)

    logger.info(
        "telegram publishing complete",
        extra={
            "workspace": workspace,
            "delivered": delivered,
            "moderation": moderated,
            "channels": len(channels),
        },
    )
    return {
        "delivered": delivered,
        "moderation": moderated,
        "channels": len(channels),
    }


@celery_app.task(bind=True, name="app.pipeline.tasks.run_workspace_pipeline")
def run_workspace_pipeline(self, workspace: str) -> Dict[str, Any]:
    """Execute the full pipeline for the given workspace."""

    config = get_workspace_config(workspace)
    ensure_dashboard(workspace)

    if not config.enabled:
        logger.info(
            "workspace pipeline disabled, skipping run",
            extra={"workspace": workspace},
        )
        return {"workspace": workspace, "published": 0, "disabled": True}

    started = time.perf_counter()
    try:
        raw_payloads = parse_news.apply(args=(workspace,)).get()
        processed_payloads = (
            process_news.apply(args=(workspace, raw_payloads)).get()
            if raw_payloads
            else []
        )
        classified_payloads = (
            classify_news.apply(args=(workspace, processed_payloads)).get()
            if processed_payloads
            else []
        )
        publication = (
            publish_news.apply(args=(workspace, classified_payloads)).get()
            if classified_payloads
            else {"published": 0}
        )
        dispatch = (
            publish_to_telegram.apply(
                args=(
                    workspace,
                    classified_payloads,
                    config.retry_attempts,
                    config.retry_delay_seconds,
                )
            ).get()
            if classified_payloads
            else {"delivered": 0, "moderation": 0, "channels": 0}
        )
        duration = time.perf_counter() - started
        published = publication.get("published", 0)
        delivered = dispatch.get("delivered", 0)
        moderated = dispatch.get("moderation", 0)

        record_pipeline_success(
            workspace,
            duration,
            published,
            delivered=delivered,
            moderated=moderated,
        )
        alerting_client.notify_success(workspace, published)
        logger.info(
            "pipeline execution completed",
            extra={
                "workspace": workspace,
                "duration": duration,
                "published": published,
                "delivered": delivered,
                "moderation": moderated,
            },
        )
        return {
            "workspace": workspace,
            "published": published,
            "delivered": delivered,
            "moderation": moderated,
            "duration": duration,
        }
    except Exception as exc:
        duration = time.perf_counter() - started
        record_pipeline_failure(workspace, duration)
        alerting_client.notify_failure(workspace, str(exc))
        logger.exception(
            "pipeline execution failed",
            extra={"workspace": workspace},
        )

        if self.request.retries >= config.retry_attempts:
            raise

        raise self.retry(
            exc=exc,
            countdown=config.retry_delay_seconds,
            max_retries=config.retry_attempts,
        )


__all__ = [
    "parse_news",
    "process_news",
    "classify_news",
    "publish_news",
    "publish_to_telegram",
    "run_workspace_pipeline",
]
