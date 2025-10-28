"""Test fixtures for the application."""
from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app

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

    yield

    session = TestingSessionLocal()
    session.close()
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
