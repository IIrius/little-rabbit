"""Test fixtures for the application."""
from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.config import get_settings
from app.database import Base, get_session
from app.main import app

os.environ.setdefault("ENCRYPTION_KEY", "BYPHtIuWGHNirMRHkRkNvztNFVQVw1Gc7YCOUMIqFZs=")
os.environ.setdefault("RATE_LIMIT_MAX_REQUESTS", "100")
os.environ.setdefault("RATE_LIMIT_WINDOW_SECONDS", "60")
os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key")

SQLALCHEMY_TEST_URL = "sqlite+pysqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def _override_get_session() -> Generator:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True, scope="function")
def setup_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_session] = _override_get_session

    pipeline_tasks_module = None
    original_session_factory = None
    try:
        from app.pipeline import tasks as pipeline_tasks_module  # noqa: E402
    except ImportError:
        pipeline_tasks_module = None
    else:
        original_session_factory = pipeline_tasks_module.SessionLocal
        pipeline_tasks_module.SessionLocal = TestingSessionLocal

    from app.pipeline.config import load_workspace_configs  # noqa: E402
    from app.services import telegram as telegram_service  # noqa: E402

    load_workspace_configs.cache_clear()
    get_settings.cache_clear()
    telegram_service.set_telegram_publisher(None)

    yield

    telegram_service.set_telegram_publisher(None)
    load_workspace_configs.cache_clear()
    get_settings.cache_clear()

    session = TestingSessionLocal()
    session.close()
    Base.metadata.drop_all(bind=engine)
    rate_limiter = getattr(app.state, "rate_limiter", None)
    if rate_limiter is not None:
        rate_limiter.reset()
    app.dependency_overrides.pop(get_session, None)
    if pipeline_tasks_module is not None and original_session_factory is not None:
        pipeline_tasks_module.SessionLocal = original_session_factory


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app, base_url="https://testserver") as client:
        yield client


@pytest.fixture()
def db_session() -> Generator:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
