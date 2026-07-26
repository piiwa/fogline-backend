from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base_class import Base
from app.db.session import get_db
from app.main import app

# A dedicated in-memory database, created per test.
#
# Tests MUST NOT import the application engine: it is bound to DATABASE_URL, so
# a developer with a hosted DSN in .env would have `make test` drop and recreate
# the real schema. StaticPool keeps every session on the same in-memory
# connection, which is what makes ":memory:" usable across a request lifecycle.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def token_for(client: AsyncClient, device_id: str = "device-A") -> str:
    res = await client.post("/api/v1/auth/device", json={"device_id": device_id})
    assert res.status_code == 200
    return res.json()["access_token"]
