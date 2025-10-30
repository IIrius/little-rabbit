from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Set


class DeliveryStrategy(str, Enum):
    WEBHOOK = "webhook"
    POLLING = "polling"


@dataclass
class WorkspaceTelegramConfig:
    workspace_id: str
    token: str
    strategy: DeliveryStrategy
    webhook_url: Optional[str] = None
    allowed_channel_ids: Set[str] = field(default_factory=set)
    bound_channel_id: Optional[str] = None

    def is_channel_allowed(self, channel_id: str) -> bool:
        if not self.allowed_channel_ids:
            return True
        return channel_id in self.allowed_channel_ids
