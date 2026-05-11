"""PymuPDF converter — text-native PDF → markdown via pymupdf4llm.

Fast and pure-Python; the right pick for digital-born PDFs. Scanned PDFs
should be routed to Marker (ticket 8b) for OCR.

We import pymupdf / pymupdf4llm lazily because their SWIG-generated C
extensions clash with pytest's assertion rewriter at import time on
macOS aarch64. Lazy loading also keeps cold startup quick when only the
EPUB or DOCX paths are exercised.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from app.converters.base import BaseConverter, ConversionResult, sanitise_filename
from app.converters.errors import (
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
)


class PymuPdfConverter(BaseConverter):
    """Convert text-native PDFs to GitHub-flavoured markdown."""

    name = "pymupdf"
    supported_extensions = frozenset({".pdf"})

    DEFAULT_TIMEOUT_SECONDS = 300

    def __init__(self, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        try:
            import pymupdf  # noqa: F401
            import pymupdf4llm  # noqa: F401
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

        try:
            import pymupdf
            import pymupdf4llm
        except ImportError as exc:
            raise ConverterUnavailableError(str(exc)) from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        stem = sanitise_filename(input_path.stem)
        output_path = output_dir / f"{uuid.uuid4().hex}_{stem}.md"

        started = time.monotonic()
        try:
            with pymupdf.open(str(input_path)) as doc:
                page_count = doc.page_count
                if page_count == 0:
                    raise ConversionError("PDF has zero pages")
            markdown = pymupdf4llm.to_markdown(str(input_path))
        except pymupdf.FileDataError as exc:
            raise ConversionError(f"PDF parse error: {exc}") from exc

        duration = time.monotonic() - started

        if not isinstance(markdown, str) or not markdown.strip():
            raise ConversionError(
                "pymupdf4llm returned empty markdown — PDF may be scanned"
            )

        output_path.write_text(markdown, encoding="utf-8")

        return ConversionResult(
            output_path=output_path,
            converter=self.name,
            pages=page_count,
            size_bytes=output_path.stat().st_size,
            duration_seconds=round(duration, 3),
        )
