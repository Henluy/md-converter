"""SQLAlchemy ORM models — mirror the Drizzle schema in apps/web/lib/schema.ts.

Drizzle owns migrations; Python only reads/writes existing tables.
Any column drift will surface in CI integration tests against Postgres.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
)


class Base(MappedAsDataclass, DeclarativeBase):
    """Declarative base — dataclass-style for nicer reprs."""


class JobStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"
    #: Multi-file job where some files converted and at least one failed.
    partial_success = "partial_success"


class FileStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class QualityLevel(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class JobRow(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'processing', 'done', 'failed', "
            "'partial_success')",
            name="jobs_status_valid",
        ),
        Index("jobs_status_idx", "status"),
        Index("jobs_created_at_idx", text("created_at DESC NULLS LAST")),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        init=False,
    )
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="pending",
        default="pending",
    )
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        init=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        default=None,
    )
    error_message: Mapped[str | None] = mapped_column(String, default=None)
    total_files: Mapped[int | None] = mapped_column(
        Integer, server_default="0", default=0
    )
    processed_files: Mapped[int | None] = mapped_column(
        Integer, server_default="0", default=0
    )

    files: Mapped[list[FileRow]] = relationship(
        "FileRow",
        back_populates="job",
        cascade="all, delete-orphan",
        default_factory=list,
    )


class FileRow(Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'processing', 'done', 'failed')",
            name="files_status_valid",
        ),
        Index("files_job_id_idx", "job_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        init=False,
    )
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    stored_filename: Mapped[str] = mapped_column(String, nullable=False)
    original_format: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    output_path: Mapped[str | None] = mapped_column(String, default=None)
    converter_used: Mapped[str | None] = mapped_column(String, default=None)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, default=None)
    pages: Mapped[int | None] = mapped_column(Integer, default=None)
    # Per-file lifecycle — lets a multi-file job report partial success and
    # surface exactly which file failed and why.
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="pending",
        default="pending",
    )
    error_message: Mapped[str | None] = mapped_column(String, default=None)
    # Conversion-quality signals (see app.processors.quality).
    warnings: Mapped[list[str] | None] = mapped_column(JSONB, default=None)
    quality_score: Mapped[float | None] = mapped_column(Float, default=None)
    quality_level: Mapped[str | None] = mapped_column(String, default=None)
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        init=False,
    )

    job: Mapped[JobRow] = relationship(
        "JobRow", back_populates="files", default=None
    )
