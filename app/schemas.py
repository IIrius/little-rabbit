"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import AnyUrl, BaseModel, HttpUrl, constr, validator

from app.models import PipelineRunStatus, ProxyProtocol, SourceKind
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


class WorkspaceSourceBase(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=120)
    kind: SourceKind
    endpoint: HttpUrl | None = None
    is_active: bool = True

    @validator("name", pre=True)
    def _sanitize_name(cls, value: str | None) -> str:
        sanitized = sanitize_text(value)
        if not sanitized:
            raise ValueError("name cannot be blank")
        return sanitized

    @validator("kind", pre=True)
    def _validate_kind(cls, value: SourceKind | str) -> SourceKind:
        try:
            return SourceKind(value)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError("invalid source kind") from exc


class WorkspaceSourceCreate(WorkspaceSourceBase):
    pass


class WorkspaceSourceUpdate(WorkspaceSourceBase):
    pass


class WorkspaceSourceRead(WorkspaceSourceBase):
    id: int
    workspace: str
    created_at: datetime

    class Config:
        orm_mode = True


class WorkspaceProxyBase(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=120)
    protocol: ProxyProtocol
    address: AnyUrl
    is_active: bool = True

    @validator("name", pre=True)
    def _sanitize_name(cls, value: str | None) -> str:
        sanitized = sanitize_text(value)
        if not sanitized:
            raise ValueError("name cannot be blank")
        return sanitized

    @validator("protocol", pre=True)
    def _validate_protocol(cls, value: ProxyProtocol | str) -> ProxyProtocol:
        try:
            return ProxyProtocol(value)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError("invalid proxy protocol") from exc


class WorkspaceProxyCreate(WorkspaceProxyBase):
    pass


class WorkspaceProxyUpdate(WorkspaceProxyBase):
    pass


class WorkspaceProxyRead(WorkspaceProxyBase):
    id: int
    workspace: str
    created_at: datetime

    class Config:
        orm_mode = True


class WorkspaceTelegramChannelBase(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=120)
    chat_id: constr(strip_whitespace=True, min_length=1, max_length=64)
    is_active: bool = True

    @validator("name", "chat_id", pre=True)
    def _sanitize_fields(cls, value: str | None) -> str:
        sanitized = sanitize_text(value)
        if not sanitized:
            raise ValueError("field cannot be blank")
        return sanitized

    @validator("chat_id")
    def _validate_chat_id(cls, value: str) -> str:
        if value.startswith("@"):
            if len(value) <= 1:
                raise ValueError("chat_id must include characters after '@'")
            return value
        if value.isdigit():
            return value
        raise ValueError("chat_id must be numeric or start with '@'")


class WorkspaceTelegramChannelCreate(WorkspaceTelegramChannelBase):
    pass


class WorkspaceTelegramChannelUpdate(WorkspaceTelegramChannelBase):
    pass


class WorkspaceTelegramChannelRead(WorkspaceTelegramChannelBase):
    id: int
    workspace: str
    created_at: datetime

    class Config:
        orm_mode = True


class PipelineRunRead(BaseModel):
    id: int
    workspace: str
    task_id: str
    status: PipelineRunStatus
    message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class WorkspaceDashboardCounts(BaseModel):
    sources: int
    proxies: int
    telegram_channels: int
    pipeline_runs: int


class WorkspaceDashboardSnapshot(BaseModel):
    workspace: str
    counts: WorkspaceDashboardCounts
    sources: list[WorkspaceSourceRead]
    proxies: list[WorkspaceProxyRead]
    telegram_channels: list[WorkspaceTelegramChannelRead]
    pipeline_runs: list[PipelineRunRead]
