"""Job + File persistence operations (called from the Celery worker).

The Celery task delegates DB writes here so the task body stays focused
on conversion. All functions take an explicit ``Session`` — the caller
owns the transaction boundary (typically ``sync_session_scope``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.converters import ConversionResult
from app.models.db import FileRow, JobRow, JobStatus


class JobValidationError(Exception):
    """Raised when create_job inputs violate the configured batch limits."""


@dataclass(frozen=True, slots=True)
class NewFileSpec:
    """Payload passed when creating a job."""

    original_filename: str
    stored_filename: str  # UUID-prefixed name on disk
    original_format: str  # lower-case, dot-prefixed
    storage_path: str  # relative to settings.data_dir
    size_bytes: int | None = None


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def create_job(session: Session, files: list[NewFileSpec]) -> JobRow:
    """Persist a new job and its file rows in a single transaction.

    Enforces BRIEF §10 batch limits before any row is written:
      - ``max_files_per_job``
      - ``max_job_size_mb`` (sum of ``size_bytes`` for files that provided one)

    Returns the job row (with its UUID populated and the FileRow children
    accessible via ``job.files`` after a refresh).
    """
    if not files:
        raise ValueError("create_job: cannot create a job with zero files")

    settings = get_settings()
    if len(files) > settings.max_files_per_job:
        raise JobValidationError(
            f"too many files in one job: {len(files)} > "
            f"max_files_per_job={settings.max_files_per_job}"
        )

    job_size_bytes = sum(f.size_bytes or 0 for f in files)
    job_size_limit = settings.max_job_size_mb * 1024 * 1024
    if job_size_bytes > job_size_limit:
        raise JobValidationError(
            f"job is {job_size_bytes} bytes; limit is {job_size_limit} "
            f"({settings.max_job_size_mb} MB)"
        )

    job = JobRow(
        status=JobStatus.pending.value,
        total_files=len(files),
        processed_files=0,
    )
    session.add(job)
    session.flush()  # populate job.id

    job.files = [
        FileRow(
            job_id=job.id,
            original_filename=spec.original_filename,
            stored_filename=spec.stored_filename,
            original_format=spec.original_format,
            storage_path=spec.storage_path,
            size_bytes=spec.size_bytes,
        )
        for spec in files
    ]
    session.flush()
    session.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def get_job(session: Session, job_id: UUID) -> JobRow | None:
    return session.get(JobRow, job_id)


def get_file(session: Session, file_id: UUID) -> FileRow | None:
    return session.get(FileRow, file_id)


def list_jobs(
    session: Session,
    *,
    limit: int = 20,
    offset: int = 0,
) -> list[JobRow]:
    """Return jobs ordered by ``created_at`` DESC (newest first)."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    stmt = (
        select(JobRow)
        .order_by(JobRow.created_at.desc().nulls_last())
        .limit(limit)
        .offset(offset)
    )
    rows = session.scalars(stmt).all()
    # Trigger relationship load before the session closes; the route serialises
    # each ``job.files`` synchronously.
    for job in rows:
        _ = job.files
    return list(rows)


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


def start_file(session: Session, file_id: UUID) -> FileRow:
    """Mark a file's job as processing and return the file row.

    Idempotent: if the job is already processing/done/failed we leave it
    alone. We never downgrade a status that's already terminal.
    """
    file_row = session.get(FileRow, file_id)
    if file_row is None:
        raise LookupError(f"file_id={file_id} not found")

    session.execute(
        update(JobRow)
        .where(JobRow.id == file_row.job_id)
        .where(JobRow.status == JobStatus.pending.value)
        .values(status=JobStatus.processing.value)
    )
    return file_row


def complete_file(
    session: Session,
    file_id: UUID,
    result: ConversionResult,
    *,
    converter_name: str,
    output_relative_path: str,
) -> FileRow:
    """Persist a successful conversion's output and bump processed_files."""
    file_row = session.get(FileRow, file_id)
    if file_row is None:
        raise LookupError(f"file_id={file_id} not found")

    file_row.output_path = output_relative_path
    file_row.converter_used = converter_name
    file_row.size_bytes = result.size_bytes
    file_row.pages = result.pages

    session.execute(
        update(JobRow)
        .where(JobRow.id == file_row.job_id)
        .values(processed_files=JobRow.processed_files + 1)
    )
    return file_row


def fail_file(
    session: Session,
    file_id: UUID,
    *,
    error_message: str,
) -> FileRow:
    """Record a conversion failure on the parent job."""
    file_row = session.get(FileRow, file_id)
    if file_row is None:
        raise LookupError(f"file_id={file_id} not found")

    session.execute(
        update(JobRow)
        .where(JobRow.id == file_row.job_id)
        .values(
            status=JobStatus.failed.value,
            error_message=error_message,
            completed_at=datetime.now(UTC),
        )
    )
    return file_row


def recompute_job_status(session: Session, job_id: UUID) -> JobStatus:
    """Move a job to ``done`` once all its files completed successfully.

    ``failed`` is set immediately by :func:`fail_file`; this helper only
    handles the success → done transition.
    """
    job = session.get(JobRow, job_id)
    if job is None:
        raise LookupError(f"job_id={job_id} not found")

    if job.status == JobStatus.failed.value:
        return JobStatus.failed

    files_count = session.scalar(
        select(JobRow.total_files).where(JobRow.id == job_id)
    ) or 0
    processed = job.processed_files or 0

    if files_count and processed >= files_count:
        job.status = JobStatus.done.value
        job.completed_at = datetime.now(UTC)
        return JobStatus.done

    return JobStatus(job.status)
