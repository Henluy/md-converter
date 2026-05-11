"""MarkItDown converter — fallback for docx / html / txt.

MarkItDown brings in onnxruntime + numpy + magika transitively, which can
clash with other native extensions at import time. We construct the engine
lazily on first use to keep cold-start quick.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from app.converters.base import BaseConverter, ConversionResult, sanitise_filename
from app.converters.errors import (
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
)


class MarkItDownConverter(BaseConverter):
    """Convert docx / html / txt files to markdown via Microsoft's MarkItDown."""

    name = "markitdown"
    supported_extensions = frozenset({".docx", ".html", ".txt"})

    DEFAULT_TIMEOUT_SECONDS = 300

    def __init__(self, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._timeout_seconds = timeout_seconds
        self._engine: Any | None = None

    def _get_engine(self) -> Any:
        if self._engine is None:
            try:
                from markitdown import MarkItDown
            except ImportError as exc:
                raise ConverterUnavailableError(str(exc)) from exc
            self._engine = MarkItDown()
        return self._engine

    def is_available(self) -> bool:
        try:
            import markitdown  # noqa: F401
        except ImportError:
            return False
        return True

    def convert(self, input_path: Path, output_dir: Path) -> ConversionResult:
        if not self.supports(input_path):
            raise FormatNotSupportedError(
                f"{self.name} does not support {input_path.suffix!r}"
            )

        if not input_path.exists() or not input_path.is_file():
            raise ConversionError(f"Input file not found: {input_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        stem = sanitise_filename(input_path.stem)
        output_path = output_dir / f"{uuid.uuid4().hex}_{stem}.md"

        try:
            from markitdown._exceptions import MarkItDownException
        except ImportError as exc:
            raise ConverterUnavailableError(str(exc)) from exc

        engine = self._get_engine()

        started = time.monotonic()
        try:
            result = engine.convert(str(input_path))
        except MarkItDownException as exc:
            raise ConversionError(f"markitdown failed: {exc}") from exc

        duration = time.monotonic() - started
        markdown = (result.text_content or "").strip()
        if not markdown:
            raise ConversionError("markitdown returned empty output")

        output_path.write_text(markdown, encoding="utf-8")

        return ConversionResult(
            output_path=output_path,
            converter=self.name,
            size_bytes=output_path.stat().st_size,
            duration_seconds=round(duration, 3),
        )
