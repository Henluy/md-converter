"""Application settings, loaded from the repo-root .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: apps/api/app/config.py -> three levels up
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Strongly-typed settings; reads .env at repo root, then process env."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database --------------------------------------------------------
    database_url: str = Field(
        ...,
        description=(
            "Postgres connection string. asyncpg-compatible "
            "(postgresql+asyncpg://...) or stdlib (postgresql://...) — "
            "we normalise it to asyncpg in db.py."
        ),
    )

    # --- API -------------------------------------------------------------
    api_host: str = "0.0.0.0"  # noqa: S104 — listen on all in container
    api_port: int = 8000
    data_dir: Path = Field(default=REPO_ROOT / "data")
    max_file_size_mb: int = 100
    max_job_size_mb: int = 500
    max_files_per_job: int = 50
    job_timeout_seconds: int = 300

    # --- Redis / Celery --------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # --- Security --------------------------------------------------------
    cors_origins: str = "http://localhost:3000"
    rate_limit_per_minute: int = 60
    log_level: str = "INFO"

    # --- Misc ------------------------------------------------------------
    environment: str = Field(default="development")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def async_database_url(self) -> str:
        """Ensure the SQLAlchemy URL uses the asyncpg driver."""
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        return self.database_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor — call this everywhere."""
    return Settings()
