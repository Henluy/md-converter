"""Pytest fixtures.

Tests run without a real Postgres unless DATABASE_URL points to one.
We seed dummy env vars before any app import so config.Settings validates.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest

# Seed env BEFORE the app modules import settings.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session", autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    """Drop the lru_cache so each test session reads the seeded env."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """In-process AsyncClient against the FastAPI ASGI app."""
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
