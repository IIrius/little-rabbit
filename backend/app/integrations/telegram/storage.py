from __future__ import annotations

from copy import deepcopy
from typing import Dict, Optional, Protocol

from .models import WorkspaceTelegramConfig


class WorkspaceTelegramStore(Protocol):
    def save(self, config: WorkspaceTelegramConfig) -> None:
        ...

    def get(self, workspace_id: str) -> Optional[WorkspaceTelegramConfig]:
        ...


class InMemoryWorkspaceTelegramStore:
    def __init__(self) -> None:
        self._configs: Dict[str, WorkspaceTelegramConfig] = {}

    def save(self, config: WorkspaceTelegramConfig) -> None:
        self._configs[config.workspace_id] = deepcopy(config)

    def get(self, workspace_id: str) -> Optional[WorkspaceTelegramConfig]:
        config = self._configs.get(workspace_id)
        if config is None:
            return None
        return deepcopy(config)
