"""The conversion Celery task — DB-aware (ticket 10).

Flow:

  1. Load the :class:`FileRow` referenced by ``file_id``.
  2. Mark its job as ``processing`` (idempotent).
  3. Validate the on-disk file, route to the right converter, convert.
  4. Persist the output path / converter / size / pages and increment
     ``jobs.processed_files``; once all files are done, mark the job ``done``.
  5. On any failure, mark the job ``failed`` with an error message and
     re-raise so Celery records the task as failed.

The CLI keeps the queue-less, persistence-less path (it talks to the
converters directly), which stays useful for local debugging.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.config import get_settings
from app.converters import (
    ConversionError,
    ConversionResult,
    ConverterRouter,
    ConverterUnavailableError,
    FormatNotSupportedError,
    build_default_registry,
)
from app.db_sync import sync_session_scope
from app.security import (
    FileValidationError,
    PathTraversalError,
    safe_resolve_relative,
    validate_upload,
)
from app.services import (
    complete_file,
    fail_file,
    get_file,
    recompute_job_status,
    start_file,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _result_to_payload(
    result: ConversionResult,
    *,
    converter_name: str,
    target_format: str,
    detected_mime: str,
    file_id: str,
    job_id: str,
) -> dict[str, Any]:
    """JSON-friendly representation (Celery result backend stores JSON)."""
    return {
        "file_id": file_id,
        "job_id": job_id,
        "output_path": str(result.output_path),
        "converter": converter_name,
        "target_format": target_format,
        "detected_mime": detected_mime,
        "pages": result.pages,
        "size_bytes": result.size_bytes,
        "duration_seconds": result.duration_seconds,
        "warnings": list(result.warnings),
    }


def _resolve_output_dir(settings_data_dir: Path, job_id: UUID) -> Path:
    out = settings_data_dir / "output" / str(job_id)
    out.mkdir(parents=True, exist_ok=True)
    return out


@celery_app.task(  # type: ignore[untyped-decorator]
    name="md-converter.convert_file",
    bind=True,
    autoretry_for=(),
    max_retries=0,
    acks_late=True,
)
def convert_file_task(
    self: Any,
    *,
    file_id: str,
    override: str | None = None,
) -> dict[str, Any]:
    """Run one file conversion + persist results."""
    settings = get_settings()
    file_uuid = UUID(file_id)
    job_uuid: UUID | None = None
    input_path: Path | None = None

    # ---- 1. Load file row + mark job processing ------------------------
    with sync_session_scope() as session:
        file_row = get_file(session, file_uuid)
        if file_row is None:
            raise LookupError(f"file_id={file_id} not found")
        job_uuid = file_row.job_id
        try:
            input_path = safe_resolve_relative(
                settings.data_dir, file_row.storage_path
            )
        except PathTraversalError as exc:
            fail_file(
                session,
                file_uuid,
                error_message=f"PathTraversalError: {exc}",
            )
            raise
        start_file(session, file_uuid)

    assert job_uuid is not None
    assert input_path is not None

    logger.info(
        "task=%s start file_id=%s job_id=%s input=%s",
        self.request.id, file_id, job_uuid, input_path,
    )

    output_dir = _resolve_output_dir(settings.data_dir, job_uuid)

    # ---- 2. Validate + route + convert ---------------------------------
    try:
        detected = validate_upload(input_path)
        router = ConverterRouter(build_default_registry())
        decision = router.resolve(input_path, override=override)
        try:
            result = decision.converter.convert(input_path, output_dir)
        except SoftTimeLimitExceeded as exc:
            raise ConversionError("Converter exceeded the soft time limit") from exc
    except (
        ConversionError,
        ConverterUnavailableError,
        FormatNotSupportedError,
        FileValidationError,
        PathTraversalError,
    ) as exc:
        logger.exception("task=%s conversion failed", self.request.id)
        with sync_session_scope() as session:
            fail_file(session, file_uuid, error_message=f"{type(exc).__name__}: {exc}")
        raise

    # ---- 3. Persist success --------------------------------------------
    output_relative = str(result.output_path.relative_to(settings.data_dir))
    with sync_session_scope() as session:
        complete_file(
            session,
            file_uuid,
            result,
            converter_name=decision.converter_name,
            output_relative_path=output_relative,
        )
        recompute_job_status(session, job_uuid)

    logger.info(
        "task=%s done file_id=%s output=%s bytes=%d",
        self.request.id, file_id, result.output_path, result.size_bytes,
    )
    return _result_to_payload(
        result,
        converter_name=decision.converter_name,
        target_format=str(decision.target_format),
        detected_mime=detected.mime_type,
        file_id=str(file_uuid),
        job_id=str(job_uuid),
    )
