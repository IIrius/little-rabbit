"""Celery tasks that orchestrate news ingestion pipelines."""
from __future__ import annotations

import time
from typing import Any, Dict, List
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import NewsArticle
from app.observability.alerts import alerting_client
from app.observability.logging import get_logger
from app.observability.metrics import (
    record_pipeline_failure,
    record_pipeline_success,
)
from app.observability.monitoring import ensure_dashboard
from app.pipeline.config import get_workspace_config
from app.security.sanitization import sanitize_text

logger = get_logger("pipeline.tasks")


def _slugify(value: str) -> str:
    processed = [
        char.lower() if char.isalnum() else "-"
        for char in value.strip()
    ]
    slug = "".join(processed)
    slug = "-".join(filter(None, slug.split("-")))
    if not slug:
        slug = f"article-{uuid4().hex}"
    return slug[:255]


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
        publication = (
            publish_news.apply(args=(workspace, processed_payloads)).get()
            if processed_payloads
            else {"published": 0}
        )
        duration = time.perf_counter() - started
        published = publication.get("published", 0)

        record_pipeline_success(workspace, duration, published)
        alerting_client.notify_success(workspace, published)
        logger.info(
            "pipeline execution completed",
            extra={
                "workspace": workspace,
                "duration": duration,
                "published": published,
            },
        )
        return {
            "workspace": workspace,
            "published": published,
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
    "publish_news",
    "run_workspace_pipeline",
]
