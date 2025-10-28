"""Database models."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
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
