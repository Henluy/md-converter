"""Pandoc converter — EPUB → GitHub-flavoured markdown.

We shell out to the ``pandoc`` binary because the python bindings (pypandoc)
are a thin wrapper anyway and we'd lose control over the args we need
(`--wrap=none`, `--extract-media`, timeouts, stderr capture).
"""

from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from pathlib import Path

from app.converters.base import BaseConverter, ConversionResult, sanitise_filename
from app.converters.errors import (
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
)


class PandocConverter(BaseConverter):
    """EPUB → markdown via the pandoc binary."""

    name = "pandoc"
    supported_extensions = frozenset({".epub"})

    DEFAULT_TIMEOUT_SECONDS = 300
    OUTPUT_FORMAT = "gfm+footnotes+task_lists"

    def __init__(
        self,
        *,
        binary: str | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._binary = binary or shutil.which("pandoc") or "pandoc"
        self._timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------
    # BaseConverter API
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        return shutil.which(self._binary) is not None

    def convert(self, input_path: Path, output_dir: Path) -> ConversionResult:
        if not self.is_available():
            raise ConverterUnavailableError(
                "pandoc binary not found — install it (e.g. `brew install pandoc`)."
            )

        if not self.supports(input_path):
            raise FormatNotSupportedError(
                f"{self.name} does not support {input_path.suffix!r}; "
                f"expected one of {sorted(self.supported_extensions)}"
            )

        if not input_path.exists() or not input_path.is_file():
            raise ConversionError(f"Input file not found: {input_path}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # On-disk filename is UUID-prefixed (collision-free, no traversal).
        stem = sanitise_filename(input_path.stem)
        output_path = output_dir / f"{uuid.uuid4().hex}_{stem}.md"
        media_dir = output_dir / f"{output_path.stem}_media"

        cmd = [
            self._binary,
            "--from=epub",
            f"--to={self.OUTPUT_FORMAT}",
            "--wrap=none",
            "--standalone",
            f"--extract-media={media_dir}",
            "--output",
            str(output_path),
            str(input_path),
        ]

        started = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603 — args are fully controlled
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ConversionError(
                f"pandoc timed out after {self._timeout_seconds}s",
                stderr=str(exc),
            ) from exc
        except FileNotFoundError as exc:
            raise ConverterUnavailableError(str(exc)) from exc

        duration = time.monotonic() - started

        if completed.returncode != 0:
            raise ConversionError(
                "pandoc returned a non-zero exit code",
                returncode=completed.returncode,
                stderr=completed.stderr,
            )

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise ConversionError(
                "pandoc exited successfully but produced no output",
                stderr=completed.stderr,
            )

        warnings = [
            line for line in completed.stderr.splitlines() if line.strip()
        ]

        return ConversionResult(
            output_path=output_path,
            converter=self.name,
            size_bytes=output_path.stat().st_size,
            duration_seconds=round(duration, 3),
            warnings=warnings,
        )
