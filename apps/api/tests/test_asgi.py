"""ASGI app smoke test (httpx + ASGITransport, per 005-fastapi-python.mdc)."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_health_httpx_asgi() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "healthy"
