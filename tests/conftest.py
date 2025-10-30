from __future__ import annotations

import os
from collections.abc import AsyncIterator, Generator

import fakeredis
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault(
    "ENCRYPTION_KEY", "BYPHtIuWGHNirMRHkRkNvztNFVQVw1Gc7YCOUMIqFZs="
)
os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key")
os.environ.setdefault("RATE_LIMIT_MAX_REQUESTS", "100")
os.environ.setdefault("RATE_LIMIT_WINDOW_SECONDS", "60")

from app.config import get_settings  # noqa: E402
from app.database import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()

TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture(scope="session")
def engine() -> Generator:
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="session")
def session_factory(engine) -> sessionmaker:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


@pytest.fixture(scope="function")
def db_session(session_factory, engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session: Session = session_factory(bind=connection)

    session.begin_nested()

    def restart_savepoint(_session: Session, transaction) -> None:
        if transaction.nested and not getattr(transaction._parent, "nested", False):
            _session.expire_all()
            _session.begin_nested()

    event.listen(session, "after_transaction_end", restart_savepoint)

    try:
        yield session
    finally:
        event.remove(session, "after_transaction_end", restart_savepoint)
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def override_db_dependency(db_session: Session) -> Generator[None, None, None]:
    def _get_test_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)
        limiter = getattr(app.state, "rate_limiter", None)
        if limiter is not None:
            limiter.reset()


@pytest.fixture()
def redis_client() -> Generator[fakeredis.FakeRedis, None, None]:
    client = fakeredis.FakeRedis(decode_responses=True)
    app.state.redis = client
    try:
        yield client
    finally:
        client.flushall()
        try:
            delattr(app.state, "redis")
        except AttributeError:
            app.state.redis = None


@pytest_asyncio.fixture()
async def async_client(
    override_db_dependency, redis_client
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


@pytest.fixture()
def user_factory(db_session: Session):
    from tests import factories

    def create_user(**kwargs):
        password = kwargs.pop("password", "Password123!")
        user = factories.UserFactory.create(
            session=db_session, plain_password=password, **kwargs
        )
        return user, password

    return create_user
