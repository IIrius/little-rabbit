from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models import ProcessingOutcome, ProcessingRecord
from app.pipeline.tasks import (
    deduplicate_news,
    detect_fake_news,
    score_news,
    translate_news,
    _fingerprint_content,
)
from app.services.deepseek import DeepSeekClient, set_deepseek_client
from app.services.memory import MemoryService, set_memory_service


def _base_item(slug: str, title: str, body: str, *, summary: str | None = None) -> dict[str, Any]:
    summary = summary or title
    return {
        "slug": slug,
        "title": title,
        "summary": summary,
        "body": body,
        "author": "bot",
    }


def test_deduplicate_news_marks_duplicates() -> None:
    set_memory_service(MemoryService())

    first = _base_item("alpha-entry", "Alpha headline", "Alpha body text")
    second = _base_item("alpha-entry", "Alpha headline", "Alpha body text")

    result = deduplicate_news.run("acme", [first, second])

    assert len(result) == 2
    first_result, second_result = result
    assert first_result["deduplication"]["is_duplicate"] is False
    assert second_result["deduplication"]["is_duplicate"] is True
    assert second_result["deduplication"]["reason"] == "duplicate-within-run"
    assert second_result["record_reference"].startswith(second_result["slug"])


def test_translate_news_invokes_deepseek() -> None:
    calls: list[dict[str, Any]] = []

    class StubDeepSeek(DeepSeekClient):
        def adapt_content(self, title: str, summary: str, body: str, *, target_language: str | None = None) -> dict[str, str]:  # type: ignore[override]
            calls.append({
                "title": title,
                "summary": summary,
                "body": body,
                "target_language": target_language,
            })
            language = (target_language or "en").lower()
            return {
                "title": f"translated {title}",
                "summary": f"translated {summary}",
                "body": f"translated {body}",
                "language": language,
            }

    set_deepseek_client(StubDeepSeek())

    unique = _base_item("unique", "Source", "Body")
    duplicate = _base_item("duplicate", "Source", "Body")
    duplicate["deduplication"] = {
        "is_duplicate": True,
        "reason": "duplicate-within-run",
        "matched_reference": None,
        "matched_record_id": None,
        "record_reference": "duplicate::dup",
    }

    translated = translate_news.run(
        "workspace",
        [
            {"deduplication": {"is_duplicate": False}, **unique},
            duplicate,
        ],
        "es",
    )

    assert calls, "expected DeepSeek adapt_content to be called"
    assert calls[0]["target_language"] == "es"
    assert translated[0]["translation"]["language"] == "es"
    assert translated[1]["translation"]["skipped"] is True

    set_deepseek_client(DeepSeekClient())


def test_detect_fake_news_counts_flagged() -> None:
    class StubDeepSeek(DeepSeekClient):
        def detect_fake(self, text: str) -> dict[str, Any]:  # type: ignore[override]
            is_fake = text.startswith("FLAG")
            return {
                "is_fake": is_fake,
                "confidence": 0.95 if is_fake else 0.05,
                "rationale": "stub",
            }

    set_deepseek_client(StubDeepSeek())

    safe_item = {
        "translation": {"body": "all clear", "title": "safe", "summary": "safe", "language": "en", "skipped": False},
        "deduplication": {"is_duplicate": False},
    }
    fake_item = {
        "translation": {"body": "FLAG suspicious", "title": "flag", "summary": "flag", "language": "en", "skipped": False},
        "deduplication": {"is_duplicate": False},
    }

    analysed = detect_fake_news.run("acme", [safe_item, fake_item])

    assert analysed[0]["fake_detection"]["is_fake"] is False
    assert analysed[1]["fake_detection"]["is_fake"] is True
    assert analysed[1]["fake_detection"]["confidence"] == 0.95

    set_deepseek_client(DeepSeekClient())


def test_score_news_routes_actions_and_persists(db_session) -> None:
    set_memory_service(MemoryService())

    publish_item = _base_item("publish-me", "Launch update", "All systems normal")
    publish_item["fingerprint"] = _fingerprint_content(publish_item)
    publish_item["record_reference"] = publish_item["slug"]
    publish_item["deduplication"] = {
        "is_duplicate": False,
        "reason": None,
        "matched_reference": None,
        "matched_record_id": None,
        "record_reference": publish_item["slug"],
    }
    publish_item["translation"] = {
        "title": publish_item["title"],
        "summary": publish_item["summary"],
        "body": publish_item["body"],
        "language": "en",
        "skipped": False,
    }
    publish_item["fake_detection"] = {
        "is_fake": False,
        "confidence": 0.0,
        "rationale": "stub",
        "skipped": False,
    }

    moderate_item = _base_item(
        "moderate-me",
        "Policy breach reported",
        "Policy breach requires review",
    )
    moderate_item["fingerprint"] = _fingerprint_content(moderate_item)
    moderate_item["record_reference"] = moderate_item["slug"]
    moderate_item["deduplication"] = {
        "is_duplicate": False,
        "reason": None,
        "matched_reference": None,
        "matched_record_id": None,
        "record_reference": moderate_item["slug"],
    }
    moderate_item["translation"] = {
        "title": moderate_item["title"],
        "summary": moderate_item["summary"],
        "body": moderate_item["body"],
        "language": "en",
        "skipped": False,
    }
    moderate_item["fake_detection"] = {
        "is_fake": False,
        "confidence": 0.0,
        "rationale": "stub",
        "skipped": False,
    }

    fake_item = _base_item("fake-me", "Alert", "Deepfake detected in footage")
    fake_item["fingerprint"] = _fingerprint_content(fake_item)
    fake_item["record_reference"] = fake_item["slug"]
    fake_item["deduplication"] = {
        "is_duplicate": False,
        "reason": None,
        "matched_reference": None,
        "matched_record_id": None,
        "record_reference": fake_item["slug"],
    }
    fake_item["translation"] = {
        "title": fake_item["title"],
        "summary": fake_item["summary"],
        "body": fake_item["body"],
        "language": "en",
        "skipped": False,
    }
    fake_item["fake_detection"] = {
        "is_fake": True,
        "confidence": 0.9,
        "rationale": "stub",
        "skipped": False,
    }

    duplicate_item = _base_item("publish-me", "Launch update", "All systems normal")
    duplicate_item["fingerprint"] = _fingerprint_content(duplicate_item)
    duplicate_suffix = f"::{duplicate_item['fingerprint'][:12]}"
    duplicate_base = duplicate_item["slug"]
    if len(duplicate_base) + len(duplicate_suffix) > 255:
        duplicate_base = duplicate_base[: 255 - len(duplicate_suffix)]
    duplicate_reference = f"{duplicate_base}{duplicate_suffix}"
    duplicate_item["record_reference"] = duplicate_reference
    duplicate_item["deduplication"] = {
        "is_duplicate": True,
        "reason": "duplicate-within-run",
        "matched_reference": None,
        "matched_record_id": None,
        "record_reference": duplicate_reference,
    }
    duplicate_item["translation"] = {
        "title": duplicate_item["title"],
        "summary": duplicate_item["summary"],
        "body": duplicate_item["body"],
        "language": "en",
        "skipped": True,
    }
    duplicate_item["fake_detection"] = {
        "is_fake": False,
        "confidence": 0.0,
        "rationale": "Skipped due to duplicate content",
        "skipped": True,
    }

    results = score_news.run("acme", [publish_item, moderate_item, fake_item, duplicate_item])

    actions = {entry["processing"]["reference"]: entry["processing"]["action"] for entry in results}

    assert actions[publish_item["slug"]] == ProcessingOutcome.PUBLISH.value
    assert actions[moderate_item["slug"]] == ProcessingOutcome.MODERATE.value
    assert actions[fake_item["slug"]] == ProcessingOutcome.REJECT.value
    assert actions[duplicate_reference] == ProcessingOutcome.REJECT.value

    records = (
        db_session.execute(
            select(ProcessingRecord).where(ProcessingRecord.workspace == "acme")
        )
        .scalars()
        .all()
    )
    assert len(records) == 4

    outcome_map = {record.reference: record.outcome for record in records}
    assert outcome_map[publish_item["slug"]] is ProcessingOutcome.PUBLISH
    assert outcome_map[moderate_item["slug"]] is ProcessingOutcome.MODERATE
    assert outcome_map[fake_item["slug"]] is ProcessingOutcome.REJECT
    assert outcome_map[duplicate_reference] is ProcessingOutcome.REJECT

    for record in records:
        assert record.logs is not None
        assert record.outcome.value in record.logs
