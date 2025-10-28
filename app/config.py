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

    class Config:
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    env_file = os.environ.get("ENV_FILE")
    if env_file:
        return Settings(_env_file=env_file)
    return Settings(_env_file=".env")
