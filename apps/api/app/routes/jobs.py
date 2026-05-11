"""Job-creation endpoint.

``POST /jobs`` accepts multipart-encoded files, validates each one,
persists them to ``/data/input/{uuid}_{stem}{ext}``, creates a job row
together with one file row per upload, and dispatches a Celery task per
file. The HTTP response returns the freshly-created job for the client
to poll (ticket 13 will add ``GET /jobs/{id}``).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.config import get_settings
from app.converters.base import sanitise_filename
from app.db_sync import sync_session_scope
from app.models.api import FileRead, JobRead
from app.models.db import FileRow, JobRow
from app.security import (
    FileTooLargeError,
    FileValidationError,
    MimeTypeMismatchError,
    PathTraversalError,
    UnsupportedExtensionError,
    safe_resolve_relative,
    validate_upload,
)
from app.services import (
    JobValidationError,
    NewFileSpec,
    create_job,
    get_job,
    list_jobs,
)
from app.tasks import convert_file_task

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


def _job_to_read(job: JobRow) -> JobRead:
    """Hand-roll the response: avoids loading related FileRows lazily after
    the session closes."""
    return JobRead(
        id=job.id,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        total_files=job.total_files or 0,
        processed_files=job.processed_files or 0,
        files=[_file_to_read(f) for f in job.files],
    )


def _file_to_read(file: FileRow) -> FileRead:
    return FileRead(
        id=file.id,
        job_id=file.job_id,
        original_filename=file.original_filename,
        original_format=file.original_format,
        converter_used=file.converter_used,
        output_path=file.output_path,
        size_bytes=file.size_bytes,
        pages=file.pages,
        created_at=file.created_at,
    )


async def _stash_upload(
    upload: UploadFile,
    *,
    data_dir: Path,
    max_bytes: int,
) -> tuple[Path, str, int]:
    """Stream the upload to ``/data/input/{uuid}_{sanitised}`` and return
    (absolute_path, relative_path, size_bytes). The on-disk name is
    UUID-prefixed so it can never collide with a user-controlled name.
    """
    original_name = upload.filename or "upload.bin"
    suffix = Path(original_name).suffix.lower()
    safe_stem = sanitise_filename(Path(original_name).stem)
    stored_filename = f"{uuid.uuid4().hex}_{safe_stem}{suffix}"

    relative_path = f"input/{stored_filename}"
    absolute_path = safe_resolve_relative(data_dir, relative_path)
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with absolute_path.open("wb") as out:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                # Cleanly remove the partial file before raising.
                out.close()
                absolute_path.unlink(missing_ok=True)
                raise FileTooLargeError(
                    f"file {original_name!r} is bigger than {max_bytes} bytes"
                )
            out.write(chunk)
    return absolute_path, relative_path, total


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversion job from one or more uploaded files",
)
async def create_job_route(
    files: list[UploadFile] = File(  # noqa: B008 — FastAPI dependency-injected default
        ..., description="Up to 50 files (max 100 MB each).",
    ),
) -> JobRead:
    settings = get_settings()
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no files provided")
    if len(files) > settings.max_files_per_job:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"too many files: {len(files)} > max_files_per_job={settings.max_files_per_job}",
        )

    data_dir = settings.data_dir
    max_bytes_per_file = settings.max_file_size_mb * 1024 * 1024
    specs: list[NewFileSpec] = []
    staged_paths: list[Path] = []

    # ---- 1. Stash every upload + validate ------------------------------
    try:
        for upload in files:
            absolute, relative, size_bytes = await _stash_upload(
                upload, data_dir=data_dir, max_bytes=max_bytes_per_file
            )
            staged_paths.append(absolute)
            try:
                detected = validate_upload(absolute, max_file_size_mb=settings.max_file_size_mb)
            except (
                UnsupportedExtensionError,
                MimeTypeMismatchError,
                FileTooLargeError,
                FileValidationError,
            ) as exc:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"{upload.filename}: {exc}",
                ) from exc

            specs.append(
                NewFileSpec(
                    original_filename=upload.filename or absolute.name,
                    stored_filename=absolute.name,
                    original_format=detected.extension,
                    storage_path=relative,
                    size_bytes=size_bytes,
                )
            )
    except (FileTooLargeError, PathTraversalError) as exc:
        # Clean any partial files staged before the failure surfaced.
        for p in staged_paths:
            p.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    # ---- 2. Persist the job row ----------------------------------------
    job_id: UUID
    try:
        with sync_session_scope() as session:
            job = create_job(session, specs)
            job_id = job.id
            response = _job_to_read(job)
            file_ids = [f.id for f in job.files]
    except JobValidationError as exc:
        for p in staged_paths:
            p.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    # ---- 3. Dispatch one task per file ---------------------------------
    for file_id in file_ids:
        convert_file_task.delay(file_id=str(file_id))
        logger.info("dispatched file_id=%s for job_id=%s", file_id, job_id)

    return response


@router.get(
    "",
    response_model=list[JobRead],
    summary="List recent jobs (newest first)",
)
async def list_jobs_route(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[JobRead]:
    with sync_session_scope() as session:
        return [_job_to_read(j) for j in list_jobs(session, limit=limit, offset=offset)]


@router.get(
    "/{job_id}",
    response_model=JobRead,
    summary="Fetch a job and its files",
)
async def get_job_route(job_id: UUID) -> JobRead:
    with sync_session_scope() as session:
        job = get_job(session, job_id)
        if job is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
        return _job_to_read(job)
