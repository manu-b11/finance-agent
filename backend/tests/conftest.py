import os
from collections.abc import AsyncGenerator

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://finanzas:finanzas@localhost:5432/finanzas")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import models
from app.core.config import settings
from app.core.database import Base, get_session
from app.main import app


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = make_url(settings.database_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


@pytest.fixture
async def engine():
    engine = create_async_engine(_test_database_url(), poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
