"""Application configuration helpers."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = Field("Deployment Service", env="APP_NAME")
    app_env: str = Field("development", env="APP_ENV")
    database_url: str = Field(
        "postgresql+psycopg2://app:app@localhost:5432/app", env="DATABASE_URL"
    )
    docs_output_path: str = Field("docs/openapi.json", env="DOCS_OUTPUT_PATH")
    rate_limit_max_requests: int = Field(100, env="RATE_LIMIT_MAX_REQUESTS")
    rate_limit_window_seconds: int = Field(60, env="RATE_LIMIT_WINDOW_SECONDS")
    audit_log_path: str = Field("logs/audit.log", env="AUDIT_LOG_PATH")
    vault_addr: str | None = Field(None, env="VAULT_ADDR")
    vault_token: str | None = Field(None, env="VAULT_TOKEN")
    vault_verify: bool = Field(True, env="VAULT_VERIFY")
    vault_secret_path: str = Field("secret/data/app", env="VAULT_SECRET_PATH")
    vault_encryption_key_field: str = Field(
        "ENCRYPTION_KEY", env="VAULT_ENCRYPTION_KEY_FIELD"
    )
    celery_broker_url: str = Field("memory://", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field("rpc://", env="CELERY_RESULT_BACKEND")
    pipeline_config_json: str | None = Field(None, env="WORKSPACE_PIPELINES_JSON")
    telegram_bot_token: str | None = Field(None, env="TELEGRAM_BOT_TOKEN")
    telegram_api_base_url: str = Field(
        "https://api.telegram.org", env="TELEGRAM_API_BASE_URL"
    )
    telegram_timeout_seconds: float = Field(5.0, env="TELEGRAM_TIMEOUT_SECONDS")
    auth_secret_key: str = Field("change-me", env="AUTH_SECRET_KEY")
    access_token_expire_minutes: int = Field(15, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(
        60 * 24 * 7, env="REFRESH_TOKEN_EXPIRE_MINUTES"
    )
    password_reset_token_expire_minutes: int = Field(
        30, env="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES"
    )

    class Config:
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    env_file = os.environ.get("ENV_FILE")
    if env_file:
        return Settings(_env_file=env_file)
    return Settings(_env_file=".env")
