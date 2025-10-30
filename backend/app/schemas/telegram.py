from __future__ import annotations

from typing import List, Optional, cast

from pydantic import BaseModel, Field, HttpUrl, validator

from app.integrations.telegram.models import (
    DeliveryStrategy,
    WorkspaceTelegramConfig,
)


class RegisterBotRequest(BaseModel):
    token: str = Field(..., min_length=1)
    strategy: DeliveryStrategy
    webhook_url: Optional[HttpUrl] = None
    allowed_channel_ids: List[str] = Field(default_factory=list)

    @validator("webhook_url", always=True)
    def _validate_webhook_requirements(
        cls, webhook_url: Optional[HttpUrl], values: dict[str, object]
    ) -> Optional[HttpUrl]:
        strategy = values.get("strategy")
        if strategy == DeliveryStrategy.WEBHOOK and webhook_url is None:
            raise ValueError("webhook_url is required when strategy is webhook")
        return webhook_url


class BindChannelRequest(BaseModel):
    channel_id: str = Field(..., min_length=1)


class WorkspaceTelegramConfigResponse(BaseModel):
    workspace_id: str
    strategy: DeliveryStrategy
    webhook_url: Optional[HttpUrl] = None
    allowed_channel_ids: List[str] = Field(default_factory=list)
    bound_channel_id: Optional[str] = None

    @classmethod
    def from_config(
        cls, config: WorkspaceTelegramConfig
    ) -> "WorkspaceTelegramConfigResponse":
        return cls(
            workspace_id=config.workspace_id,
            strategy=config.strategy,
            webhook_url=cast(Optional[HttpUrl], config.webhook_url),
            allowed_channel_ids=sorted(config.allowed_channel_ids),
            bound_channel_id=config.bound_channel_id,
        )
