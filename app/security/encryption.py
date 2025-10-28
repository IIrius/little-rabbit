"""Helpers for data-at-rest encryption."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.security.vault import (
    VaultIntegrationError,
    VaultSecretNotFound,
    get_vault_client,
)

LOGGER = logging.getLogger(__name__)


class DataEncryptor:
    """Wrapper around Fernet symmetric encryption."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, value: str | None) -> str | None:
        """Encrypt a string value, returning a base64 token."""

        if value is None:
            return None
        token = self._fernet.encrypt(value.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, token: str | None) -> str | None:
        """Decrypt a base64 token back to its original string value."""

        if token is None:
            return None
        try:
            plaintext = self._fernet.decrypt(token.encode("utf-8"))
        except InvalidToken as exc:  # pragma: no cover - defensive branch
            raise ValueError("Unable to decrypt data with configured key") from exc
        return plaintext.decode("utf-8")


def _normalise_key(raw_key: str) -> bytes:
    key_bytes = raw_key.encode("utf-8")
    try:
        Fernet(key_bytes)
    except ValueError:
        digest = hashlib.sha256(key_bytes).digest()
        key_bytes = base64.urlsafe_b64encode(digest)
    return key_bytes


@lru_cache(maxsize=1)
def get_data_encryptor() -> DataEncryptor:
    """Return a cached encryptor loaded from Vault or environment."""

    settings = get_settings()
    vault_client = get_vault_client()
    env_key = os.getenv("ENCRYPTION_KEY")

    try:
        key = vault_client.get_secret(
            settings.vault_secret_path,
            settings.vault_encryption_key_field,
            default=env_key,
        )
    except (VaultSecretNotFound, VaultIntegrationError):
        key = env_key

    if key is None:
        generated = Fernet.generate_key().decode("utf-8")
        os.environ["ENCRYPTION_KEY"] = generated
        LOGGER.warning(
            "Generated ephemeral encryption key; configure a persistent key via "
            "Vault or the ENCRYPTION_KEY environment variable."
        )
        key = generated

    normalised = _normalise_key(key)
    return DataEncryptor(normalised)
