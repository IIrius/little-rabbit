from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_session
from app.security.authentication import (
    allowed_workspaces,
    consume_password_reset_token,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    ensure_workspace_access,
    find_refresh_token,
    get_current_user,
    hash_password,
    require_roles,
    rotate_refresh_token,
    validate_requested_workspaces,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_memberships(user: models.User) -> list[schemas.WorkspaceMembership]:
    return [
        schemas.WorkspaceMembership(
            workspace=membership.workspace,
            role=membership.role.value,
        )
        for membership in sorted(user.workspaces, key=lambda item: item.workspace)
    ]


def _user_payload(user: models.User) -> schemas.UserPublic:
    return schemas.UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        default_workspace=user.default_workspace,
        workspaces=_user_memberships(user),
    )


def _issue_token_pair(
    session: Session, user: models.User, *, workspace: str | None = None
) -> schemas.AuthTokenPair:
    access_token, access_expires = create_access_token(
        user, workspace=workspace or user.default_workspace
    )
    refresh_token, refresh_expires = create_refresh_token(session, user)
    session.flush()
    return schemas.AuthTokenPair(
        access_token=access_token,
        access_token_expires_at=access_expires,
        refresh_token=refresh_token,
        refresh_token_expires_at=refresh_expires,
        user=_user_payload(user),
    )


@router.get("/available-workspaces")
def list_available_workspaces() -> dict[str, list[str]]:
    return {"workspaces": list(allowed_workspaces())}


@router.post(
    "/register",
    response_model=schemas.AuthTokenPair,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: schemas.AuthRegisterRequest, session: Session = Depends(get_session)
) -> schemas.AuthTokenPair:
    existing = session.execute(
        select(models.User).where(models.User.email == payload.email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    try:
        role = models.UserRole(payload.role)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown role",
        ) from exc

    workspaces = validate_requested_workspaces(payload.workspaces)
    hashed_password = hash_password(payload.password)
    user = models.User(
        email=payload.email,
        hashed_password=hashed_password,
        full_name=payload.full_name,
        role=role,
        default_workspace=workspaces[0] if workspaces else None,
    )
    session.add(user)
    session.flush()

    for workspace in workspaces:
        membership = models.UserWorkspace(
            user_id=user.id,
            workspace=workspace,
            role=role,
        )
        session.add(membership)

    token_pair = _issue_token_pair(session, user)
    session.commit()
    return token_pair


@router.post("/login", response_model=schemas.AuthTokenPair)
def login(
    payload: schemas.AuthLoginRequest, session: Session = Depends(get_session)
) -> schemas.AuthTokenPair:
    user = session.execute(
        select(models.User).where(models.User.email == payload.email)
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    token_pair = _issue_token_pair(session, user)
    session.commit()
    return token_pair


@router.post("/refresh", response_model=schemas.AuthTokenPair)
def refresh_session(
    payload: schemas.AuthRefreshRequest, session: Session = Depends(get_session)
) -> schemas.AuthTokenPair:
    token_record = find_refresh_token(session, payload.refresh_token)
    if token_record is None or token_record.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    now = datetime.now(timezone.utc)
    if token_record.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )
    user = token_record.user
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    new_refresh, refresh_expires = rotate_refresh_token(session, token_record, user)
    access_token, access_expires = create_access_token(
        user, workspace=user.default_workspace
    )
    session.flush()
    session.commit()
    return schemas.AuthTokenPair(
        access_token=access_token,
        access_token_expires_at=access_expires,
        refresh_token=new_refresh,
        refresh_token_expires_at=refresh_expires,
        user=_user_payload(user),
    )


@router.get("/me", response_model=schemas.UserPublic)
def current_user(
    current: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> schemas.UserPublic:
    user = session.get(models.User, current.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_payload(user)


@router.post("/workspaces/select", response_model=schemas.UserPublic)
def select_workspace(
    payload: schemas.WorkspaceSelectionRequest,
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> schemas.UserPublic:
    user = session.get(models.User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    ensure_workspace_access(user, payload.workspace)
    user.default_workspace = payload.workspace
    session.commit()
    session.refresh(user)
    return _user_payload(user)


@router.get("/workspaces", response_model=dict[str, list[schemas.WorkspaceMembership]])
def list_user_workspaces(
    current_user: models.User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, list[schemas.WorkspaceMembership]]:
    user = session.get(models.User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"workspaces": _user_memberships(user)}


@router.post("/password-reset/request")
def request_password_reset(
    payload: schemas.PasswordResetRequest, session: Session = Depends(get_session)
) -> dict[str, object]:
    user = session.execute(
        select(models.User).where(models.User.email == payload.email)
    ).scalar_one_or_none()
    if user is None:
        return {
            "message": "If the account exists, a reset link has been generated.",
            "reset_token": None,
        }
    token, expires_at = create_password_reset_token(session, user)
    session.commit()
    return {
        "message": "Reset token generated.",
        "reset_token": token,
        "expires_at": expires_at,
    }


@router.post("/password-reset/confirm")
def confirm_password_reset(
    payload: schemas.PasswordResetConfirmation,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    record = consume_password_reset_token(session, payload.token)
    user = record.user
    user.hashed_password = hash_password(payload.new_password)
    session.flush()
    session.commit()
    return {"message": "Password updated"}


@router.get("/guarded/admin")
def admin_guard(
    _: models.User = Depends(require_roles(models.UserRole.ADMIN)),
) -> dict[str, str]:
    return {"status": "ok"}
