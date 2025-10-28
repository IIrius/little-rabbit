"""Helpers for interacting with a secrets vault."""
from __future__ import annotations

import os
from functools import lru_cache

from app.config import get_settings

try:
    import hvac  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    hvac = None


class VaultIntegrationError(RuntimeError):
    """Raised when communication with the vault fails."""


class VaultSecretNotFound(VaultIntegrationError):
    """Raised when a requested secret key cannot be located."""


class VaultClient:
    """Minimal wrapper around HashiCorp Vault (or environment fallbacks)."""

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        verify: bool = True,
    ) -> None:
        self.url = url or os.getenv("VAULT_ADDR")
        self.token = token or os.getenv("VAULT_TOKEN")
        self.verify = verify
        self._client = None

        if hvac is not None and self.url and self.token:
            try:
                self._client = hvac.Client(  # type: ignore[no-untyped-call]
                    url=self.url, token=self.token, verify=self.verify
                )
            except Exception as exc:  # pragma: no cover - network errors
                raise VaultIntegrationError("Unable to initialise Vault client") from exc

    def get_secret(self, path: str, key: str, default: str | None = None) -> str:
        """Return a secret value from the configured source."""

        env_candidates = [
            f"VAULT_SECRET_{_normalise_env_key(path)}_{key.upper()}",
            key.upper(),
        ]
        for env_var in env_candidates:
            value = os.getenv(env_var)
            if value is not None:
                return value

        if self._client is not None and self._client.is_authenticated():
            try:
                response = self._client.secrets.kv.v2.read_secret_version(path=path)
            except Exception as exc:  # pragma: no cover - network errors
                if default is not None:
                    return default
                raise VaultIntegrationError(
                    f"Unable to read secret at path '{path}'"
                ) from exc

            data = response.get("data", {}).get("data", {})
            if key in data:
                return str(data[key])

        if default is not None:
            return default

        raise VaultSecretNotFound(
            f"Secret key '{key}' not available via environment or Vault path '{path}'"
        )


def _normalise_env_key(path: str) -> str:
    return path.upper().replace("/", "_").replace("-", "_")


@lru_cache(maxsize=1)
def get_vault_client() -> VaultClient:
    """Return a cached Vault client instance."""

    settings = get_settings()
    return VaultClient(
        url=settings.vault_addr,
        token=settings.vault_token,
        verify=settings.vault_verify,
    )
