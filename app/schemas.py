"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator

from app.security.sanitization import sanitize_text


class ItemCreate(BaseModel):
    name: str
    description: Optional[str] = None

    @validator("name", "description", pre=True)
    def _sanitize(cls, value: Optional[str]) -> Optional[str]:
        return sanitize_text(value)


class ItemRead(ItemCreate):
    id: int

    class Config:
        orm_mode = True


class ModerationAIAnalysis(BaseModel):
    score: float
    summary: str
    flags: List[str] = Field(default_factory=list)

    @validator("summary", pre=True)
    def _sanitize_summary(cls, value: Optional[str]) -> str:
        cleaned = sanitize_text(value)
        return cleaned or ""

    @validator("flags", pre=True)
    def _sanitize_flags(cls, value: Optional[List[str]]) -> List[str]:
        if value is None:
            return []
        sanitized: List[str] = []
        for entry in value:
            cleaned = sanitize_text(entry)
            if cleaned:
                sanitized.append(cleaned)
        return sanitized


class ModerationRequestRead(BaseModel):
    id: int
    workspace: str
    reference: str
    status: str
    submitted_at: datetime
    content_title: str
    content_excerpt: Optional[str]
    ai_analysis: ModerationAIAnalysis

    _sanitize_workspace = validator("workspace", pre=True)(sanitize_text)
    _sanitize_reference = validator("reference", pre=True)(sanitize_text)
    _sanitize_title = validator("content_title", pre=True)(sanitize_text)
    _sanitize_excerpt = validator("content_excerpt", pre=True)(sanitize_text)

    class Config:
        orm_mode = True


class ModerationDecisionCreate(BaseModel):
    decision: str
    reason: Optional[str] = None
    actor: Optional[str] = Field(default=None, alias="decided_by")

    @validator("decision")
    def _validate_decision(cls, value: str) -> str:
        cleaned = (sanitize_text(value) or "").lower()
        if cleaned not in {"approved", "rejected"}:
            raise ValueError("decision must be either 'approved' or 'rejected'")
        return cleaned

    _sanitize_reason = validator("reason", pre=True, allow_reuse=True)(sanitize_text)
    _sanitize_actor = validator("actor", pre=True, allow_reuse=True)(sanitize_text)


class ModerationBulkDecision(ModerationDecisionCreate):
    request_ids: List[int]

    @validator("request_ids")
    def _validate_ids(cls, value: List[int]) -> List[int]:
        if not value:
            raise ValueError("request_ids cannot be empty")
        unique_ids = list(dict.fromkeys(value))
        return unique_ids


class ModerationDecisionRead(BaseModel):
    id: int
    request_id: int
    decision: str
    decided_at: datetime
    decided_by: Optional[str]
    reason: Optional[str]

    _sanitize_decision = validator("decision", pre=True)(sanitize_text)
    _sanitize_decided_by = validator("decided_by", pre=True)(sanitize_text)
    _sanitize_reason = validator("reason", pre=True)(sanitize_text)

    class Config:
        orm_mode = True
