"""Test fixtures.

Strategy
========
- Run each test against an in-memory SQLite database (aiosqlite) using a
  single connection (StaticPool) so the schema is visible across sessions
  in the same test.
- Recreate the schema once per test for hard isolation. Fast since it's
  in-memory.
- Override `get_db` so the API uses the same session the test holds.
- Monkey-patch `AsyncSessionLocal` so background tasks (e.g. the activity
  logger) write into the same test database, not production.
"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core import database as db_module
from app.main import app
from app.models.base import Base
from app.services import activity_service as activity_module

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[Any, None]:
    eng = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    # Background tasks open their own session via AsyncSessionLocal — point
    # both the source module and the already-imported reference in
    # activity_service at the test factory.
    monkeypatch.setattr(db_module, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(activity_module, "AsyncSessionLocal", session_factory)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── User / auth fixtures ─────────────────────────────────────────────────────

TEST_EMAIL = "tester@example.com"
TEST_PASSWORD = "supersecret123"


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict[str, Any]:
    resp = await client.post(
        "/api/auth/signup",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": "Test User",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def auth_headers(
    client: AsyncClient, registered_user: dict[str, Any]
) -> dict[str, str]:
    resp = await client.post(
        "/api/auth/login",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
