from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_telegram_client
from app.schemas.telegram import (
    BindChannelRequest,
    RegisterBotRequest,
    WorkspaceTelegramConfigResponse,
)
from app.telegram import (
    TelegramChannelBindingError,
    TelegramClient,
    TelegramClientError,
    TelegramConfigurationError,
    TelegramPermissionError,
    TelegramWorkspaceNotRegisteredError,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/telegram", tags=["telegram"])


def _raise_from_client_error(exc: TelegramClientError) -> None:
    if isinstance(exc, TelegramConfigurationError):
        status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, TelegramWorkspaceNotRegisteredError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, TelegramPermissionError):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, TelegramChannelBindingError):
        status_code = status.HTTP_400_BAD_REQUEST
    else:
        status_code = status.HTTP_502_BAD_GATEWAY
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/bot", response_model=WorkspaceTelegramConfigResponse)
async def register_bot(
    workspace_id: str,
    payload: RegisterBotRequest,
    client: TelegramClient = Depends(get_telegram_client),
) -> WorkspaceTelegramConfigResponse:
    try:
        config = await client.register_bot(
            workspace_id=workspace_id,
            token=payload.token,
            strategy=payload.strategy,
            webhook_url=str(payload.webhook_url) if payload.webhook_url else None,
            allowed_channel_ids=set(payload.allowed_channel_ids),
        )
    except TelegramClientError as exc:  # pragma: no cover - defensive
        _raise_from_client_error(exc)
    return WorkspaceTelegramConfigResponse.from_config(config)


@router.post("/channel", response_model=WorkspaceTelegramConfigResponse)
async def bind_channel(
    workspace_id: str,
    payload: BindChannelRequest,
    client: TelegramClient = Depends(get_telegram_client),
) -> WorkspaceTelegramConfigResponse:
    try:
        config = await client.bind_channel(
            workspace_id=workspace_id,
            channel_id=payload.channel_id,
        )
    except TelegramClientError as exc:
        _raise_from_client_error(exc)
    return WorkspaceTelegramConfigResponse.from_config(config)


@router.get("/bot", response_model=WorkspaceTelegramConfigResponse)
async def get_bot(
    workspace_id: str,
    client: TelegramClient = Depends(get_telegram_client),
) -> WorkspaceTelegramConfigResponse:
    try:
        config = client.get_config(workspace_id)
    except TelegramClientError as exc:
        _raise_from_client_error(exc)
    return WorkspaceTelegramConfigResponse.from_config(config)
