from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import get_session

_settings = get_settings()
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_PBKDF2_ITERATIONS = 200_000
_DEFAULT_WORKSPACES: tuple[str, ...] = ("dev", "staging", "production")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        salt_hex, digest_hex = hashed_password.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    return hmac.compare_digest(expected.hex(), digest_hex)


def _access_token_expiry() -> timedelta:
    return timedelta(minutes=_settings.access_token_expire_minutes)


def _refresh_token_expiry() -> timedelta:
    return timedelta(minutes=_settings.refresh_token_expire_minutes)


def _password_reset_expiry() -> timedelta:
    return timedelta(minutes=_settings.password_reset_token_expire_minutes)


def create_access_token(
    user: models.User, *, workspace: str | None = None
) -> tuple[str, datetime]:
    now = _utcnow()
    expires_at = now + _access_token_expiry()
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if workspace is not None:
        payload["workspace"] = workspace
    token = jwt.encode(payload, _settings.auth_secret_key, algorithm="HS256")
    return token, expires_at


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(session: Session, user: models.User) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(48)
    expires_at = _utcnow() + _refresh_token_expiry()
    token_record = models.RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=expires_at,
    )
    session.add(token_record)
    session.flush()
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, _settings.auth_secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:  # pragma: no cover - handled as HTTP 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
        ) from exc
    except jwt.InvalidTokenError as exc:  # pragma: no cover - handled as HTTP 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc


def get_current_user(
    token: str = Depends(_oauth2_scheme),
    session: Session = Depends(get_session),
) -> models.User:
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    try:
        user_pk = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from None
    user = session.get(models.User, user_pk)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )
    return user


def get_optional_user(
    request: Request,
    session: Session = Depends(get_session),
) -> models.User | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    try:
        scheme, token = auth_header.split(" ", 1)
    except ValueError:
        return None
    if scheme.lower() != "bearer":
        return None
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    try:
        user_pk = int(user_id)
    except (TypeError, ValueError):
        return None
    user = session.get(models.User, user_pk)
    if user is None or not user.is_active:
        return None
    return user


def require_roles(*roles: models.UserRole) -> Callable[[models.User], models.User]:
    if not roles:
        roles = (
            models.UserRole.OPERATOR,
            models.UserRole.ADMIN,
            models.UserRole.VIEWER,
        )

    def dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


def ensure_workspace_access(user: models.User, workspace: str) -> None:
    allowed = {membership.workspace for membership in user.workspaces}
    if workspace not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace access denied",
        )


def find_refresh_token(
    session: Session, token_value: str
) -> models.RefreshToken | None:
    token_hash = _hash_token(token_value)
    return session.execute(
        select(models.RefreshToken).where(models.RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()


def rotate_refresh_token(
    session: Session, token: models.RefreshToken, user: models.User
) -> tuple[str, datetime]:
    token.revoked = True
    session.flush()
    return create_refresh_token(session, user)


def create_password_reset_token(
    session: Session, user: models.User
) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = _utcnow() + _password_reset_expiry()
    record = models.PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=expires_at,
    )
    session.add(record)
    session.flush()
    return token, expires_at


def consume_password_reset_token(
    session: Session, token_value: str
) -> models.PasswordResetToken:
    token_hash = _hash_token(token_value)
    record = session.execute(
        select(models.PasswordResetToken).where(
            models.PasswordResetToken.token_hash == token_hash
        )
    ).scalar_one_or_none()
    if record is None or record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    now = _utcnow()
    if normalize_utc(record.expires_at) < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    record.used_at = now
    session.flush()
    return record


def allowed_workspaces() -> Iterable[str]:
    return _DEFAULT_WORKSPACES


def validate_requested_workspaces(requested: Iterable[str]) -> list[str]:
    allowed = set(allowed_workspaces())
    normalized: list[str] = []
    invalid: list[str] = []
    for workspace in requested:
        lowered = workspace.lower()
        if lowered not in allowed:
            invalid.append(lowered)
        elif lowered not in normalized:
            normalized.append(lowered)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"invalid_workspaces": invalid},
        )
    return normalized
