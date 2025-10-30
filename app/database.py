"""Database session and base model utilities."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Declarative base class for ORM models."""


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_session():
    """Provide a transactional scope around a series of operations."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
