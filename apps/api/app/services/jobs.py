"""Job + File persistence operations (called from the Celery worker).

The Celery task delegates DB writes here so the task body stays focused
on conversion. All functions take an explicit ``Session`` — the caller
owns the transaction boundary (typically ``sync_session_scope``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.converters import ConversionResult
from app.models.db import FileRow, FileStatus, JobRow, JobStatus
from app.processors import QualityAssessment

# Cap how many warnings we persist per file so a chatty converter (pandoc
# can emit one stderr line per glyph issue) never bloats the row.
_MAX_WARNINGS = 50


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


def create_job(
    session: Session,
    files: list[NewFileSpec],
    *,
    target_format: str = "markdown",
) -> JobRow:
    """Persist a new job and its file rows in a single transaction.

    Enforces BRIEF §10 batch limits before any row is written:
      - ``max_files_per_job``
      - ``max_job_size_mb`` (sum of ``size_bytes`` for files that provided one)

    ``target_format`` is the conversion direction: ``markdown`` (default)
    imports a document → markdown; ``pdf``/``docx``/``epub`` export an
    uploaded markdown file to that format.

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
        target_format=target_format,
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


def delete_job(session: Session, job_id: UUID) -> list[str]:
    """Remove a job, its file rows (cascade), and return the relative paths
    that the caller should clean up on disk."""
    job = session.get(JobRow, job_id)
    if job is None:
        raise LookupError(f"job_id={job_id} not found")

    paths: list[str] = []
    for f in job.files:
        if f.storage_path:
            paths.append(f.storage_path)
        if f.output_path:
            paths.append(f.output_path)

    session.delete(job)
    return paths


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
    """Mark a file as processing (and move its job out of ``pending``).

    Idempotent: we only push the job ``pending → processing`` and never
    downgrade a status that's already terminal.
    """
    file_row = session.get(FileRow, file_id)
    if file_row is None:
        raise LookupError(f"file_id={file_id} not found")

    file_row.status = FileStatus.processing.value
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
    quality: QualityAssessment | None = None,
) -> FileRow:
    """Persist a successful conversion's output, quality and warnings."""
    file_row = session.get(FileRow, file_id)
    if file_row is None:
        raise LookupError(f"file_id={file_id} not found")

    file_row.output_path = output_relative_path
    file_row.converter_used = converter_name
    file_row.size_bytes = result.size_bytes
    file_row.pages = result.pages
    file_row.status = FileStatus.done.value

    warnings = list(result.warnings)
    if quality is not None:
        warnings = [*quality.warnings, *warnings]
        file_row.quality_score = quality.score
        file_row.quality_level = quality.level
    file_row.warnings = warnings[:_MAX_WARNINGS] or None

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
    """Record a per-file conversion failure and bump the processed counter.

    The *job's* status is left to :func:`recompute_job_status` so a batch can
    still end as ``partial_success`` when other files convert fine.
    """
    file_row = session.get(FileRow, file_id)
    if file_row is None:
        raise LookupError(f"file_id={file_id} not found")

    file_row.status = FileStatus.failed.value
    file_row.error_message = error_message

    session.execute(
        update(JobRow)
        .where(JobRow.id == file_row.job_id)
        .values(processed_files=JobRow.processed_files + 1)
    )
    return file_row


def compute_job_status(*, total: int, succeeded: int, failed: int) -> JobStatus:
    """Decide a job's status from its per-file tallies. Pure / DB-free.

    - nothing to do yet → ``pending``
    - some files still running → ``processing``
    - every file converted → ``done``
    - every file failed → ``failed``
    - a mix of both → ``partial_success``
    """
    if total <= 0:
        return JobStatus.pending
    if succeeded + failed < total:
        return JobStatus.processing
    if failed == 0:
        return JobStatus.done
    if succeeded == 0:
        return JobStatus.failed
    return JobStatus.partial_success


def recompute_job_status(session: Session, job_id: UUID) -> JobStatus:
    """Recompute and persist a job's status from its files' statuses."""
    job = session.get(JobRow, job_id)
    if job is None:
        raise LookupError(f"job_id={job_id} not found")

    # The session runs with autoflush disabled (see db_sync), so flush any
    # pending per-file status changes (from complete_file/fail_file in this
    # same transaction) before we count them — otherwise the tallies are stale.
    session.flush()

    total = job.total_files or 0
    succeeded = session.scalar(
        select(func.count())
        .select_from(FileRow)
        .where(FileRow.job_id == job_id, FileRow.status == FileStatus.done.value)
    ) or 0
    failed = session.scalar(
        select(func.count())
        .select_from(FileRow)
        .where(FileRow.job_id == job_id, FileRow.status == FileStatus.failed.value)
    ) or 0

    status = compute_job_status(total=total, succeeded=succeeded, failed=failed)
    job.status = status.value
    if status in (JobStatus.done, JobStatus.failed, JobStatus.partial_success):
        job.completed_at = datetime.now(UTC)
        if failed:
            job.error_message = f"{failed} of {total} file(s) failed to convert"
    return status
