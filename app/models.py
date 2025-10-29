"""Database models."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Item(Base):
    """Represents a simple inventory item."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)


class NewsArticle(Base):
    """News article produced by the ingestion pipeline."""

    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("workspace", "slug", name="uq_news_workspace_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text(), nullable=False)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ModerationStatus(StrEnum):
    """Enumeration of moderation decisions."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ModerationRequest(Base):
    """Content item queued for human moderation."""

    __tablename__ = "moderation_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(128), nullable=False)
    content_title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_excerpt: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[ModerationStatus] = mapped_column(
        Enum(ModerationStatus),
        default=ModerationStatus.PENDING,
        nullable=False,
        index=True,
    )
    ai_score: Mapped[float] = mapped_column(Float, nullable=False)
    ai_summary: Mapped[str] = mapped_column(Text(), nullable=False)
    ai_flags: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    decisions: Mapped[list["ModerationDecision"]] = relationship(
        "ModerationDecision",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="ModerationDecision.decided_at.desc()",
    )


class ModerationDecision(Base):
    """Audit trail of moderation outcomes."""

    __tablename__ = "moderation_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("moderation_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[ModerationStatus] = mapped_column(
        Enum(ModerationStatus), nullable=False
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decided_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    request: Mapped[ModerationRequest] = relationship(
        "ModerationRequest", back_populates="decisions"
    )
