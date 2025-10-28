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

    class Config:
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    env_file = os.environ.get("ENV_FILE")
    if env_file:
        return Settings(_env_file=env_file)
    return Settings(_env_file=".env")
