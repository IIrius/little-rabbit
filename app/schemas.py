"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import AnyUrl, BaseModel, EmailStr, Field, HttpUrl, constr, validator

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


class WorkspaceMembership(BaseModel):
    workspace: str
    role: str

    _sanitize_workspace = validator("workspace", pre=True, allow_reuse=True)(
        sanitize_text
    )
    _sanitize_role = validator("role", pre=True, allow_reuse=True)(sanitize_text)

    class Config:
        orm_mode = True


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    role: str
    default_workspace: Optional[str] = None
    workspaces: List[WorkspaceMembership] = Field(default_factory=list)

    _sanitize_full_name = validator("full_name", pre=True, allow_reuse=True)(
        sanitize_text
    )
    _sanitize_role = validator("role", pre=True, allow_reuse=True)(sanitize_text)
    _sanitize_default_workspace = validator(
        "default_workspace", pre=True, allow_reuse=True
    )(sanitize_text)

    class Config:
        orm_mode = True


class AuthTokenPair(BaseModel):
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime
    token_type: str = "bearer"
    user: UserPublic


class AuthRegisterRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=8, max_length=128)
    full_name: Optional[constr(strip_whitespace=True, max_length=255)] = None
    role: str = "operator"
    workspaces: List[str] = Field(default_factory=lambda: ["dev"])

    @validator("email", pre=True)
    def _normalize_email(cls, value: str | EmailStr) -> str:
        sanitized = sanitize_text(str(value) if value is not None else None)
        if not sanitized:
            raise ValueError("email cannot be blank")
        return sanitized.lower()

    @validator("password", pre=True)
    def _normalize_password(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("invalid password")
        stripped = value.strip()
        if len(stripped) < 8:
            raise ValueError("password must be at least 8 characters long")
        return stripped

    @validator("full_name", pre=True)
    def _sanitize_full_name(cls, value: Optional[str]) -> Optional[str]:
        return sanitize_text(value)

    @validator("role", pre=True)
    def _sanitize_role(cls, value: str) -> str:
        sanitized = sanitize_text(value)
        if not sanitized:
            raise ValueError("role cannot be blank")
        return sanitized.lower()

    @validator("workspaces", pre=True)
    def _default_workspaces(cls, value: Optional[List[str]]) -> List[str]:
        if value is None:
            return ["dev"]
        return value

    @validator("workspaces")
    def _sanitize_workspaces(cls, value: List[str]) -> List[str]:
        cleaned: list[str] = []
        for entry in value:
            sanitized = sanitize_text(entry)
            if not sanitized:
                raise ValueError("workspace cannot be blank")
            normalized = sanitized.lower()
            if normalized not in cleaned:
                cleaned.append(normalized)
        if not cleaned:
            raise ValueError("at least one workspace must be provided")
        return cleaned


class AuthLoginRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=8, max_length=128)

    @validator("email", pre=True)
    def _normalize_email(cls, value: str | EmailStr) -> str:
        sanitized = sanitize_text(str(value) if value is not None else None)
        if not sanitized:
            raise ValueError("email cannot be blank")
        return sanitized.lower()

    @validator("password", pre=True)
    def _sanitize_password(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("invalid password")
        return value.strip()


class AuthRefreshRequest(BaseModel):
    refresh_token: str

    @validator("refresh_token", pre=True)
    def _sanitize_refresh_token(cls, value: str) -> str:
        sanitized = sanitize_text(value)
        if not sanitized:
            raise ValueError("refresh_token cannot be blank")
        return sanitized


class PasswordResetRequest(BaseModel):
    email: EmailStr

    @validator("email", pre=True)
    def _normalize_reset_email(cls, value: str | EmailStr) -> str:
        sanitized = sanitize_text(str(value) if value is not None else None)
        if not sanitized:
            raise ValueError("email cannot be blank")
        return sanitized.lower()


class PasswordResetConfirmation(BaseModel):
    token: str
    new_password: constr(min_length=8, max_length=128)

    @validator("token", pre=True)
    def _sanitize_token(cls, value: str) -> str:
        sanitized = sanitize_text(value)
        if not sanitized:
            raise ValueError("token cannot be blank")
        return sanitized

    @validator("new_password", pre=True)
    def _sanitize_new_password(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("invalid password")
        return value.strip()


class WorkspaceSelectionRequest(BaseModel):
    workspace: str

    @validator("workspace", pre=True)
    def _sanitize_workspace(cls, value: str) -> str:
        sanitized = sanitize_text(value)
        if not sanitized:
            raise ValueError("workspace cannot be blank")
        return sanitized.lower()


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

    _sanitize_workspace = validator("workspace", pre=True, allow_reuse=True)(
        sanitize_text
    )
    _sanitize_reference = validator("reference", pre=True, allow_reuse=True)(
        sanitize_text
    )
    _sanitize_title = validator("content_title", pre=True, allow_reuse=True)(
        sanitize_text
    )
    _sanitize_excerpt = validator("content_excerpt", pre=True, allow_reuse=True)(
        sanitize_text
    )


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


class ModerationDecisionCreate(BaseModel):
    decision: str
    reason: Optional[str] = None
    actor: Optional[str] = None

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

    _sanitize_decision = validator("decision", pre=True, allow_reuse=True)(
        sanitize_text
    )
    _sanitize_decided_by = validator("decided_by", pre=True, allow_reuse=True)(
        sanitize_text
    )
    _sanitize_reason = validator("reason", pre=True, allow_reuse=True)(sanitize_text)

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
