"""OCR converter — scanned PDF → markdown, opt-in and fully local.

Routing classifies image-only PDFs as ``pdf_scanned`` and sends them here.
We add a searchable text layer with the ``ocrmypdf`` binary (Tesseract under
the hood — no cloud, no API cost), then hand the now-text-native PDF to the
existing PymuPDF path so images, tables and cleaning all behave identically.

Disabled by default: OCR is slow and pulls in heavy system deps, so a
deployment opts in with ``ENABLE_OCR=1``. When it's off, or the binary is
missing, ``convert`` raises a clear ``ConverterUnavailableError`` that the
worker surfaces to the user instead of failing cryptically.
"""

from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from pathlib import Path

from app.converters.base import BaseConverter, ConversionResult
from app.converters.errors import (
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
)
from app.converters.pymupdf_converter import PymuPdfConverter


class OcrPdfConverter(BaseConverter):
    """Add a text layer to a scanned PDF (ocrmypdf), then extract markdown."""

    name = "ocr"
    supported_extensions = frozenset({".pdf"})

    DEFAULT_TIMEOUT_SECONDS = 900  # OCR is slow; allow generously

    def __init__(
        self,
        *,
        enabled: bool = False,
        binary: str | None = None,
        language: str = "eng",
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        pdf_converter: PymuPdfConverter | None = None,
    ) -> None:
        self._enabled = enabled
        self._binary = binary or shutil.which("ocrmypdf") or "ocrmypdf"
        self._language = language
        self._timeout_seconds = timeout_seconds
        self._pdf_converter = pdf_converter or PymuPdfConverter()

    def is_available(self) -> bool:
        return self._enabled and shutil.which(self._binary) is not None

    def convert(self, input_path: Path, output_dir: Path) -> ConversionResult:
        if not self.supports(input_path):
            raise FormatNotSupportedError(
                f"{self.name} does not support {input_path.suffix!r}"
            )
        if not self._enabled:
            raise ConverterUnavailableError(
                "OCR for scanned PDFs is disabled — set ENABLE_OCR=1 to enable it."
            )
        if shutil.which(self._binary) is None:
            raise ConverterUnavailableError(
                f"{self._binary!r} not found — install ocrmypdf "
                "(e.g. `brew install ocrmypdf`)."
            )
        if not input_path.exists() or not input_path.is_file():
            raise ConversionError(f"Input file not found: {input_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        searchable = output_dir / f"{uuid.uuid4().hex}_ocr.pdf"

        cmd = [
            self._binary,
            "--force-ocr",  # input is image-only; OCR every page
            "--language",
            self._language,
            "--output-type",
            "pdf",
            str(input_path),
            str(searchable),
        ]

        started = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603 — args fully controlled
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            searchable.unlink(missing_ok=True)
            raise ConversionError(
                f"ocrmypdf timed out after {self._timeout_seconds}s", stderr=str(exc)
            ) from exc
        except FileNotFoundError as exc:
            raise ConverterUnavailableError(str(exc)) from exc

        if completed.returncode != 0 or not searchable.exists():
            searchable.unlink(missing_ok=True)
            raise ConversionError(
                "ocrmypdf failed to add a text layer",
                returncode=completed.returncode,
                stderr=completed.stderr,
            )

        try:
            extracted = self._pdf_converter.convert(searchable, output_dir)
        finally:
            searchable.unlink(missing_ok=True)

        duration = round(time.monotonic() - started, 3)
        warnings = [
            line for line in completed.stderr.splitlines() if line.strip()
        ]
        return ConversionResult(
            output_path=extracted.output_path,
            converter=self.name,
            pages=extracted.pages,
            size_bytes=extracted.size_bytes,
            duration_seconds=duration,
            warnings=warnings,
        )
