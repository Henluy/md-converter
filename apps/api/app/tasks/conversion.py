"""The conversion Celery task.

Scope of ticket 6: convert one file via the worker, return a JSON-friendly
ConversionResult dict. Database persistence (jobs/files rows) is layered
on top at ticket 10.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded

from app.converters import (
    BaseConverter,
    ConversionError,
    ConversionResult,
    ConverterUnavailableError,
    FormatNotSupportedError,
    PandocConverter,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Registry of factories — extended at tickets 7-8 (pymupdf, marker, markitdown)
# and consumed by the router. Kept here for ticket 6 minimal scope.
_CONVERTERS: dict[str, type[BaseConverter]] = {
    "pandoc": PandocConverter,
}


def _result_to_payload(result: ConversionResult) -> dict[str, Any]:
    """JSON-serializable representation (Celery result backend stores JSON)."""
    return {
        "output_path": str(result.output_path),
        "converter": result.converter,
        "pages": result.pages,
        "size_bytes": result.size_bytes,
        "duration_seconds": result.duration_seconds,
        "warnings": list(result.warnings),
    }


@celery_app.task(  # type: ignore[untyped-decorator]  # celery has no py.typed marker
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
    converter_name: str = "pandoc",
) -> dict[str, Any]:
    """Run one document conversion and return its result as JSON."""
    src = Path(input_path)
    dst = Path(output_dir)

    converter_cls = _CONVERTERS.get(converter_name)
    if converter_cls is None:
        raise ConverterUnavailableError(
            f"Unknown converter {converter_name!r}; available: {sorted(_CONVERTERS)}"
        )

    converter = converter_cls()

    logger.info(
        "task=%s start input=%s converter=%s",
        self.request.id, src, converter_name,
    )

    try:
        result = converter.convert(src, dst)
    except SoftTimeLimitExceeded as exc:
        logger.warning("task=%s soft time limit reached", self.request.id)
        raise ConversionError("Converter exceeded the soft time limit") from exc
    except (
        ConversionError,
        ConverterUnavailableError,
        FormatNotSupportedError,
    ):
        # Bubble up — callers (and ticket 10's persistence layer) translate
        # these into job/file status updates.
        raise

    logger.info(
        "task=%s done output=%s bytes=%d duration=%.3fs",
        self.request.id, result.output_path, result.size_bytes, result.duration_seconds,
    )
    return _result_to_payload(result)
