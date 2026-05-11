"""Liveness + readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.config import get_settings
from app.db import get_engine
from app.models.api import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe — process is up."""
    settings = get_settings()
    return HealthResponse(version=__version__, environment=settings.environment)


@router.get("/readiness", response_model=ReadinessResponse)
async def readiness() -> ReadinessResponse:
    """Readiness probe — DB reachable."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
    except Exception as exc:
        return ReadinessResponse(
            status="degraded",
            database="down",
            detail=type(exc).__name__,
        )
    return ReadinessResponse(status="ready", database="up")
