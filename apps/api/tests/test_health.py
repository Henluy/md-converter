"""Smoke tests for /health and /readiness."""

from __future__ import annotations

from httpx import AsyncClient

from app.config import get_settings


async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["environment"] == "test"
    assert "version" in payload


async def test_readiness_reports_db_status(client: AsyncClient) -> None:
    """Readiness reflects whether DATABASE_URL points to a live Postgres."""
    response = await client.get("/readiness")
    assert response.status_code == 200
    payload = response.json()

    using_placeholder = "test:test@localhost" in get_settings().database_url
    if using_placeholder:
        assert payload["status"] == "degraded"
        assert payload["database"] == "down"
    else:
        assert payload["status"] == "ready"
        assert payload["database"] == "up"
