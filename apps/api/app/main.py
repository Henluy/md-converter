"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import __version__
from app.config import get_settings
from app.db import dispose_engine
from app.routes import health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup + shutdown hooks."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger.info("md-converter API starting (env=%s)", settings.environment)
    try:
        yield
    finally:
        logger.info("md-converter API shutting down")
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{settings.rate_limit_per_minute}/minute"],
    )

    app = FastAPI(
        title="md-converter API",
        version=__version__,
        description="Local EPUB/PDF → Markdown conversion service.",
        lifespan=lifespan,
        # No stack traces in error responses.
        debug=False,
    )

    app.state.limiter = limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=600,
    )

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_req: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded", "limit": str(exc.detail)},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    app.include_router(health_router)

    return app


app = create_app()
