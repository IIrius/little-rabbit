"""Celery tasks that orchestrate news ingestion pipelines."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import (
    NewsArticle,
    ProcessingOutcome,
    ProcessingRecord,
    WorkspaceTelegramChannel,
)
from app.observability.alerts import alerting_client
from app.observability.logging import get_logger
from app.observability.metrics import (
    record_pipeline_failure,
    record_pipeline_success,
)
from app.observability.monitoring import ensure_dashboard
from app.pipeline.config import get_workspace_config
from app.security.sanitization import sanitize_text
from app.services.deepseek import get_deepseek_client
from app.services.memory import get_memory_service
from app.services.moderation import serialize_flags
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


def _fingerprint_content(item: dict[str, Any]) -> str:
    source = "|".join([item.get("title", ""), item.get("summary", ""), item.get("body", "")])
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _classification_inputs(item: dict[str, Any]) -> tuple[str, str, str]:
    translation = item.get("translation") or {}
    title = translation.get("title") or item.get("title", "")
    summary = translation.get("summary") or item.get("summary", "")
    body = translation.get("body") or item.get("body", "")
    return title, summary, body


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


@celery_app.task(bind=True, name="app.pipeline.tasks.deduplicate_news")
def deduplicate_news(
    self, workspace: str, processed_items: List[dict[str, Any]]
) -> List[dict[str, Any]]:
    """Check for duplicate content using the memory service and persisted history."""

    memory_service = get_memory_service()
    session: Session = SessionLocal()
    deduplicated: List[dict[str, Any]] = []
    duplicates = 0

    try:
        for item in processed_items:
            payload = dict(item)
            fingerprint = payload.get("fingerprint") or _fingerprint_content(payload)
            matched_record = session.execute(
                select(ProcessingRecord).where(
                    ProcessingRecord.workspace == workspace,
                    ProcessingRecord.fingerprint == fingerprint,
                )
            ).scalar_one_or_none()
            seen_in_run = memory_service.has_seen(workspace, fingerprint)
            is_duplicate = bool(matched_record or seen_in_run)
            if is_duplicate:
                duplicates += 1
            memory_service.remember(workspace, fingerprint)
            record_reference = payload["slug"]
            if matched_record is not None:
                record_reference = matched_record.reference
            elif is_duplicate:
                suffix = f"::{fingerprint[:12]}"
                base_reference = payload["slug"]
                if len(base_reference) + len(suffix) > 255:
                    base_reference = base_reference[: 255 - len(suffix)]
                record_reference = f"{base_reference}{suffix}"
            payload["fingerprint"] = fingerprint
            payload["record_reference"] = record_reference
            payload["deduplication"] = {
                "is_duplicate": is_duplicate,
                "reason": (
                    "duplicate-within-run"
                    if seen_in_run and matched_record is None
                    else "historical-duplicate"
                    if matched_record is not None
                    else None
                ),
                "matched_reference": matched_record.reference if matched_record else None,
                "matched_record_id": matched_record.id if matched_record else None,
                "record_reference": record_reference,
            }
            deduplicated.append(payload)
    finally:
        session.close()

    logger.info(
        "deduplication check complete",
        extra={"workspace": workspace, "duplicates": duplicates, "count": len(deduplicated)},
    )
    return deduplicated


@celery_app.task(bind=True, name="app.pipeline.tasks.translate_news")
def translate_news(
    self,
    workspace: str,
    deduplicated_items: List[dict[str, Any]],
    target_language: str,
) -> List[dict[str, Any]]:
    """Translate or adapt content to the workspace's target language."""

    client = get_deepseek_client()
    translated: List[dict[str, Any]] = []
    translated_count = 0
    language = (target_language or "en").lower()

    for item in deduplicated_items:
        payload = dict(item)
        dedup_info = payload.get("deduplication") or {}
        if dedup_info.get("is_duplicate"):
            translation = {
                "title": payload.get("title", ""),
                "summary": payload.get("summary", ""),
                "body": payload.get("body", ""),
                "language": language,
                "skipped": True,
            }
        else:
            translation = client.adapt_content(
                payload.get("title", ""),
                payload.get("summary", ""),
                payload.get("body", ""),
                target_language=language,
            )
            translation["skipped"] = False
            translated_count += 1
        payload["translation"] = translation
        translated.append(payload)

    logger.info(
        "translation complete",
        extra={
            "workspace": workspace,
            "language": language,
            "translated": translated_count,
            "count": len(translated),
        },
    )
    return translated


@celery_app.task(bind=True, name="app.pipeline.tasks.detect_fake_news")
def detect_fake_news(
    self, workspace: str, translated_items: List[dict[str, Any]]
) -> List[dict[str, Any]]:
    """Detect counterfeit or synthetic content using DeepSeek analysis."""

    client = get_deepseek_client()
    analysed: List[dict[str, Any]] = []
    flagged = 0

    for item in translated_items:
        payload = dict(item)
        dedup_info = payload.get("deduplication") or {}
        translation = payload.get("translation") or {}
        if dedup_info.get("is_duplicate"):
            detection = {
                "is_fake": False,
                "confidence": 0.0,
                "rationale": "Skipped due to duplicate content",
                "skipped": True,
            }
        else:
            detection = client.detect_fake(translation.get("body") or payload.get("body", ""))
            detection["skipped"] = False
            if detection.get("is_fake"):
                flagged += 1
        payload["fake_detection"] = detection
        analysed.append(payload)

    logger.info(
        "fake detection complete",
        extra={"workspace": workspace, "flagged": flagged, "count": len(analysed)},
    )
    return analysed


@celery_app.task(bind=True, name="app.pipeline.tasks.score_news")
def score_news(
    self, workspace: str, analysed_items: List[dict[str, Any]]
) -> List[dict[str, Any]]:
    """Assign final outcomes based on classification, deduplication, and detection."""

    session: Session = SessionLocal()
    scored: List[dict[str, Any]] = []
    publishable = 0
    moderated = 0
    rejected = 0
    duplicates = 0
    fake_detected = 0

    try:
        for item in analysed_items:
            payload = dict(item)
            fingerprint = payload.get("fingerprint") or _fingerprint_content(payload)
            dedup_info = payload.get("deduplication") or {}
            fake_info = payload.get("fake_detection") or {}
            record_reference = payload.get("record_reference") or payload["slug"]
            title, summary, body = _classification_inputs(payload)
            classification = classify_article(title, summary, body)
            payload["classification"] = classification.to_payload()

            action = ProcessingOutcome.PUBLISH
            reason: str | None = None

            if dedup_info.get("is_duplicate"):
                action = ProcessingOutcome.REJECT
                reason = dedup_info.get("reason") or "duplicate"
                duplicates += 1
                rejected += 1
            elif fake_info.get("is_fake"):
                action = ProcessingOutcome.REJECT
                reason = "fake_detection"
                fake_detected += 1
                rejected += 1
            elif classification.requires_moderation:
                action = ProcessingOutcome.MODERATE
                reason = "requires_moderation"
                moderated += 1
            else:
                publishable += 1

            record = session.execute(
                select(ProcessingRecord).where(
                    ProcessingRecord.workspace == workspace,
                    ProcessingRecord.reference == record_reference,
                )
            ).scalar_one_or_none()
            if record is None:
                matched_record_id = dedup_info.get("matched_record_id")
                if matched_record_id is not None:
                    record = session.get(ProcessingRecord, matched_record_id)
            if record is None:
                record = ProcessingRecord(
                    workspace=workspace,
                    reference=record_reference,
                    fingerprint=fingerprint,
                    outcome=action,
                )
                session.add(record)
            record.fingerprint = fingerprint
            record.outcome = action
            record.status_reason = reason
            record.dedup_reason = dedup_info.get("reason")
            translation = payload.get("translation") or {}
            record.translation_language = translation.get("language")
            record.fake_detected = bool(fake_info.get("is_fake"))
            record.fake_confidence = float(fake_info.get("confidence", 0.0) or 0.0)
            record.classification_score = classification.score
            record.classification_summary = classification.summary
            record.classification_flags = serialize_flags(classification.flags)
            record.logs = json.dumps(
                {
                    "deduplication": dedup_info,
                    "translation": translation,
                    "fake_detection": fake_info,
                    "classification": classification.to_payload(),
                    "action": action.value,
                    "reason": reason,
                },
                sort_keys=True,
            )
            session.flush()
            payload["processing"] = {
                "action": action.value,
                "reason": reason,
                "record_id": record.id,
                "reference": record_reference,
            }
            scored.append(payload)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info(
        "scoring complete",
        extra={
            "workspace": workspace,
            "publish": publishable,
            "moderate": moderated,
            "reject": rejected,
            "duplicates": duplicates,
            "fake_detected": fake_detected,
        },
    )
    return scored


@celery_app.task(bind=True, name="app.pipeline.tasks.classify_news")
def classify_news(
    self, workspace: str, processed_items: List[dict[str, Any]]
) -> List[dict[str, Any]]:
    """Classify processed articles to determine moderation requirements."""

    classified: List[dict[str, Any]] = []
    moderation_required = 0

    for item in processed_items:
        payload = dict(item)
        dedup_info = payload.get("deduplication") or {}
        if dedup_info.get("is_duplicate"):
            outcome = ClassificationOutcome(
                score=0.0,
                summary="Skipped due to duplicate content",
                flags=[],
                requires_moderation=False,
            )
        else:
            title, summary, body = _classification_inputs(payload)
            outcome = classify_article(title, summary, body)
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
            pipeline_state = item.get("processing") or {}
            action = pipeline_state.get("action")
            if action and action != ProcessingOutcome.PUBLISH.value:
                continue

            slug = item["slug"]
            existing = session.execute(
                select(NewsArticle).where(
                    NewsArticle.workspace == workspace,
                    NewsArticle.slug == slug,
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue

            translation = item.get("translation") or {}
            title = translation.get("title") or item["title"]
            summary = translation.get("summary") or item["summary"]
            body = translation.get("body") or item["body"]

            article = NewsArticle(
                workspace=workspace,
                slug=slug,
                title=title,
                summary=summary,
                body=body,
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
            pipeline_state = item.get("processing") or {}
            action = pipeline_state.get("action") or ProcessingOutcome.PUBLISH.value
            classification_payload = item.get("classification") or {}
            outcome = _outcome_from_payload(classification_payload)
            translation = item.get("translation") or {}

            if action == ProcessingOutcome.MODERATE.value:
                created = queue_moderation_request(
                    session,
                    workspace=workspace,
                    reference=item["slug"],
                    title=translation.get("title") or item.get("title"),
                    excerpt=translation.get("summary") or item.get("summary"),
                    outcome=outcome,
                )
                if created is not None:
                    moderated += 1
                continue

            if action != ProcessingOutcome.PUBLISH.value:
                logger.info(
                    "content rejected prior to telegram delivery",
                    extra={"workspace": workspace, "slug": item["slug"], "action": action},
                )
                continue

            if not channels or not publisher_enabled:
                continue

            message = build_telegram_message(
                translation.get("title") or item.get("title", ""),
                translation.get("summary") or item.get("summary", ""),
                item.get("author"),
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
        deduplicated_payloads = (
            deduplicate_news.apply(args=(workspace, processed_payloads)).get()
            if processed_payloads
            else []
        )
        translated_payloads = (
            translate_news.apply(
                args=(workspace, deduplicated_payloads, config.target_language)
            ).get()
            if deduplicated_payloads
            else []
        )
        analysed_payloads = (
            detect_fake_news.apply(args=(workspace, translated_payloads)).get()
            if translated_payloads
            else []
        )
        scored_payloads = (
            score_news.apply(args=(workspace, analysed_payloads)).get()
            if analysed_payloads
            else []
        )
        publication = (
            publish_news.apply(args=(workspace, scored_payloads)).get()
            if scored_payloads
            else {"published": 0}
        )
        dispatch = (
            publish_to_telegram.apply(
                args=(
                    workspace,
                    scored_payloads,
                    config.retry_attempts,
                    config.retry_delay_seconds,
                )
            ).get()
            if scored_payloads
            else {"delivered": 0, "moderation": 0, "channels": 0}
        )
        duration = time.perf_counter() - started
        published = publication.get("published", 0)
        delivered = dispatch.get("delivered", 0)
        moderated_count = dispatch.get("moderation", 0)

        rejected_items = [
            item
            for item in scored_payloads
            if (item.get("processing") or {}).get("action") == ProcessingOutcome.REJECT.value
        ]
        moderated_items = [
            item
            for item in scored_payloads
            if (item.get("processing") or {}).get("action") == ProcessingOutcome.MODERATE.value
        ]
        duplicate_count = sum(
            1
            for item in scored_payloads
            if (item.get("deduplication") or {}).get("is_duplicate")
        )
        fake_count = sum(
            1 for item in scored_payloads if (item.get("fake_detection") or {}).get("is_fake")
        )
        moderated_count = max(moderated_count, len(moderated_items))

        record_pipeline_success(
            workspace,
            duration,
            published,
            delivered=delivered,
            moderated=moderated_count,
            rejected=len(rejected_items),
            duplicates=duplicate_count,
            fake_detected=fake_count,
        )
        alerting_client.notify_success(workspace, published)
        logger.info(
            "pipeline execution completed",
            extra={
                "workspace": workspace,
                "duration": duration,
                "published": published,
                "delivered": delivered,
                "moderation": moderated_count,
                "rejected": len(rejected_items),
                "duplicates": duplicate_count,
                "fake_detected": fake_count,
                "processed": len(scored_payloads),
            },
        )
        return {
            "workspace": workspace,
            "published": published,
            "delivered": delivered,
            "moderation": moderated_count,
            "rejected": len(rejected_items),
            "duplicates": duplicate_count,
            "fake_detected": fake_count,
            "processed": len(scored_payloads),
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
        ) from exc


__all__ = [
    "parse_news",
    "process_news",
    "deduplicate_news",
    "translate_news",
    "detect_fake_news",
    "score_news",
    "classify_news",
    "publish_news",
    "publish_to_telegram",
    "run_workspace_pipeline",
]
