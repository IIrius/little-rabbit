"""Database models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression, func

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


class SourceKind(str, Enum):
    RSS = "rss"
    API = "api"
    TELEGRAM = "telegram"
    CUSTOM = "custom"


class ProxyProtocol(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


class PipelineRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"


class WorkspaceSource(Base):
    """Configurable content source for a workspace."""

    __tablename__ = "workspace_sources"
    __table_args__ = (
        UniqueConstraint("workspace", "name", name="uq_workspace_source_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[SourceKind] = mapped_column(
        SAEnum(SourceKind, name="workspace_source_kind"), nullable=False
    )
    endpoint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=expression.true(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WorkspaceProxy(Base):
    """Outbound proxy configuration for a workspace."""

    __tablename__ = "workspace_proxies"
    __table_args__ = (
        UniqueConstraint("workspace", "name", name="uq_workspace_proxy_name"),
        UniqueConstraint("workspace", "address", name="uq_workspace_proxy_address"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    protocol: Mapped[ProxyProtocol] = mapped_column(
        SAEnum(ProxyProtocol, name="workspace_proxy_protocol"), nullable=False
    )
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=expression.true(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WorkspaceTelegramChannel(Base):
    """Telegram channel registration for a workspace."""

    __tablename__ = "workspace_telegram_channels"
    __table_args__ = (
        UniqueConstraint("workspace", "name", name="uq_workspace_telegram_name"),
        UniqueConstraint("workspace", "chat_id", name="uq_workspace_telegram_chat"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=expression.true(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PipelineRun(Base):
    """Represents the execution status of a workspace pipeline run."""

    __tablename__ = "pipeline_runs"
    __table_args__ = (
        UniqueConstraint("workspace", "task_id", name="uq_pipeline_run_task"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[PipelineRunStatus] = mapped_column(
        SAEnum(PipelineRunStatus, name="pipeline_run_status"),
        nullable=False,
        default=PipelineRunStatus.QUEUED,
        server_default=PipelineRunStatus.QUEUED.value,
    )
    message: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
