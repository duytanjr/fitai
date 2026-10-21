import os
import pytest
from httpx import AsyncClient, ASGITransport

# Ensure SECRET_KEY is present for testing
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-backend-unit-testing")

from main import app


@pytest.fixture
async def async_client():
    """Asynchronous HTTP test client for FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
