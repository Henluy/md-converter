"""PymuPDF converter — text-native PDF → markdown via pymupdf4llm.

Fast and pure-Python; the right pick for digital-born PDFs. Scanned PDFs
should be routed to the OCR converter (``app.converters.ocr``).

We pass pymupdf4llm explicit, tunable options instead of relying on bare
defaults:

* ``table_strategy="lines_strict"`` keeps ruled tables intact;
* ``write_images=True`` extracts embedded raster images into a per-file
  ``…_media/`` folder, which the cleaner flattens to ``media/`` — without
  this, every image in a PDF was silently dropped;
* ``margins`` is exposed (default 0 = keep everything) so a deployment can
  trim repeating headers/footers/page numbers if it wants to.

We import pymupdf / pymupdf4llm lazily because their SWIG-generated C
extensions clash with pytest's assertion rewriter at import time on
macOS aarch64. Lazy loading also keeps cold startup quick when only the
EPUB or DOCX paths are exercised.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from app.converters.base import (
    BaseConverter,
    ConversionResult,
    sanitise_filename,
    write_cleaned_markdown,
)
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
    #: pymupdf4llm table detection strategy. "lines_strict" only treats
    #: fully-ruled cells as tables (fewer false positives than "lines").
    DEFAULT_TABLE_STRATEGY = "lines_strict"

    def __init__(
        self,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        table_strategy: str = DEFAULT_TABLE_STRATEGY,
        extract_images: bool = True,
        image_format: str = "png",
        margins: float | tuple[float, float, float, float] = 0,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._table_strategy = table_strategy
        self._extract_images = extract_images
        self._image_format = image_format
        self._margins = margins

    def is_available(self) -> bool:
        try:
            import pymupdf  # noqa: F401
            import pymupdf4llm  # noqa: F401
        except ImportError:
            return False
        return True

    def convert(self, input_path: Path, output_dir: Path) -> ConversionResult:
        if not self.supports(input_path):
            raise FormatNotSupportedError(f"{self.name} does not support {input_path.suffix!r}")

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
        # Per-file media folder; the cleaner rewrites references into the
        # flat ``media/`` form and renames this directory to match.
        media_dir = output_dir / f"{output_path.stem}_media"

        to_markdown_kwargs: dict[str, Any] = {
            "table_strategy": self._table_strategy,
            "margins": self._margins,
        }
        if self._extract_images:
            media_dir.mkdir(parents=True, exist_ok=True)
            to_markdown_kwargs.update(
                write_images=True,
                image_path=str(media_dir),
                image_format=self._image_format,
            )

        started = time.monotonic()
        try:
            with pymupdf.open(str(input_path)) as doc:
                page_count = doc.page_count
                if page_count == 0:
                    raise ConversionError("PDF has zero pages")
            markdown = pymupdf4llm.to_markdown(str(input_path), **to_markdown_kwargs)
        except pymupdf.FileDataError as exc:
            raise ConversionError(f"PDF parse error: {exc}") from exc

        duration = time.monotonic() - started

        if not isinstance(markdown, str) or not markdown.strip():
            self._discard_empty_media(media_dir)
            raise ConversionError("pymupdf4llm returned empty markdown — PDF may be scanned")

        write_cleaned_markdown(
            output_path,
            markdown,
            media_dir=media_dir if self._extract_images else None,
        )
        self._discard_empty_media(media_dir)

        return ConversionResult(
            output_path=output_path,
            converter=self.name,
            pages=page_count,
            size_bytes=output_path.stat().st_size,
            duration_seconds=round(duration, 3),
        )

    @staticmethod
    def _discard_empty_media(media_dir: Path) -> None:
        """Drop the media folder when no images were extracted (no clutter)."""
        if media_dir.is_dir() and not any(media_dir.iterdir()):
            media_dir.rmdir()
