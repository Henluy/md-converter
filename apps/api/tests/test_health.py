"""Smoke tests for /health and /readiness."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["environment"] == "test"
    assert "version" in payload


async def test_readiness_degraded_without_db(client: AsyncClient) -> None:
    """No real Postgres in unit tests → readiness must report degraded."""
    response = await client.get("/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"] == "down"
