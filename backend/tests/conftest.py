"""
conftest.py — Fixtures dùng chung cho toàn bộ test suite.

DATABASE: PostgreSQL thật (fitai_db) — cùng instance với dev.
Mỗi test chạy trong một transaction riêng được ROLLBACK sau khi kết thúc
→ không làm bẩn dữ liệu thật, không cần database riêng.

NullPool được dùng để mỗi test tạo connection mới trên event loop của nó,
tránh lỗi "Future attached to a different loop" với asyncpg.
"""
import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

# Đặt SECRET_KEY TRƯỚC khi import app để tránh ValidationError
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-backend-unit-testing")

from main import app
from core.database import get_db
from core.config import settings


@pytest.fixture
async def db_session():
    """
    AsyncSession chạy trong transaction tự rollback sau mỗi test.
    NullPool: mỗi fixture call tạo connection mới → không bị lẫn event loop giữa các test.
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()
    await engine.dispose()


@pytest.fixture
async def async_client(db_session: AsyncSession):
    """
    HTTP test client gắn với db_session (transaction tự rollback).
    Tất cả request trong một test dùng chung session → đảm bảo nhất quán.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
