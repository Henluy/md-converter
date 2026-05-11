"""Pydantic models exposed by the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Liveness — always returns ok when the process is up."""

    status: Literal["ok"] = "ok"
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    """Readiness — flips to not-ready if a dependency is broken."""

    status: Literal["ready", "degraded"]
    database: Literal["up", "down"]
    detail: str | None = None


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    original_filename: str
    original_format: str
    converter_used: str | None = None
    output_path: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    pages: int | None = Field(default=None, ge=0)
    created_at: datetime | None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: Literal["pending", "processing", "done", "failed"]
    created_at: datetime | None
    completed_at: datetime | None
    error_message: str | None = None
    total_files: int = 0
    processed_files: int = 0
    files: list[FileRead] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Standardised error envelope."""

    detail: str
    code: str | None = None
