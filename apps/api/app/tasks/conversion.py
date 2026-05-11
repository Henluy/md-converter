"""The conversion Celery task.

Ticket 6 wired the worker; ticket 7 routes the input through the
validation + router pipeline before handing it to the right converter.
Database persistence is layered on at ticket 10.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded

from app.converters import (
    ConversionError,
    ConversionResult,
    ConverterRouter,
    ConverterUnavailableError,
    FormatNotSupportedError,
    build_default_registry,
)
from app.security import FileValidationError, validate_upload
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _result_to_payload(
    result: ConversionResult,
    *,
    converter_name: str,
    target_format: str,
    detected_mime: str,
) -> dict[str, Any]:
    """JSON-friendly representation (Celery result backend stores JSON)."""
    return {
        "output_path": str(result.output_path),
        "converter": converter_name,
        "target_format": target_format,
        "detected_mime": detected_mime,
        "pages": result.pages,
        "size_bytes": result.size_bytes,
        "duration_seconds": result.duration_seconds,
        "warnings": list(result.warnings),
    }


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
    input_path: str,
    output_dir: str,
    override: str | None = None,
) -> dict[str, Any]:
    """Validate → route → convert. Errors propagate (ticket 10 handles DB)."""
    src = Path(input_path)
    dst = Path(output_dir)

    logger.info("task=%s start input=%s", self.request.id, src)

    # Validate (raises FileValidationError on rejection)
    detected = validate_upload(src)

    router = ConverterRouter(build_default_registry())
    decision = router.resolve(src, override=override)

    logger.info(
        "task=%s routed target=%s converter=%s",
        self.request.id, decision.target_format, decision.converter_name,
    )

    try:
        result = decision.converter.convert(src, dst)
    except SoftTimeLimitExceeded as exc:
        logger.warning("task=%s soft time limit reached", self.request.id)
        raise ConversionError("Converter exceeded the soft time limit") from exc
    except (
        ConversionError,
        ConverterUnavailableError,
        FormatNotSupportedError,
        FileValidationError,
    ):
        raise

    logger.info(
        "task=%s done output=%s bytes=%d duration=%.3fs",
        self.request.id, result.output_path, result.size_bytes, result.duration_seconds,
    )
    return _result_to_payload(
        result,
        converter_name=decision.converter_name,
        target_format=str(decision.target_format),
        detected_mime=detected.mime_type,
    )
