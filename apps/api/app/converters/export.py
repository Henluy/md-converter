"""Markdown → PDF / DOCX / EPUB export via the pandoc binary.

This is the reverse direction of the rest of the app: instead of turning a
document into markdown, we turn the markdown *back* into a distributable
file. Pandoc handles DOCX and EPUB natively; PDF goes through an HTML/CSS
engine (WeasyPrint by default) so we don't need a multi-gigabyte LaTeX
toolchain on the host.

DOCX/EPUB need only the ``pandoc`` binary. PDF additionally needs the PDF
engine to be installed — when it's missing, ``convert`` raises a clear
``ConverterUnavailableError`` (same contract as the OCR converter) rather
than failing cryptically deep inside pandoc.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import uuid
from enum import StrEnum
from pathlib import Path

from app.converters.base import (
    BaseConverter,
    ConversionResult,
    sanitise_filename,
)
from app.converters.errors import (
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
)


class OutputFormat(StrEnum):
    """Target format a job converts *to*.

    ``markdown`` is the default import direction (any document → markdown);
    the others are export targets handled by :class:`MarkdownExportConverter`.
    """

    markdown = "markdown"
    pdf = "pdf"
    docx = "docx"
    epub = "epub"


#: Export targets and the on-disk extension pandoc writes for each. ``markdown``
#: is deliberately absent — it is the import direction, not an export target.
_EXPORT_EXTENSIONS: dict[OutputFormat, str] = {
    OutputFormat.pdf: ".pdf",
    OutputFormat.docx: ".docx",
    OutputFormat.epub: ".epub",
}

# macOS/Homebrew installs the Pango/GLib dylibs WeasyPrint needs under
# /opt/homebrew/lib, which isn't on the default loader path. Prepending it to
# DYLD_FALLBACK_LIBRARY_PATH lets WeasyPrint find libgobject etc. On Linux the
# directory doesn't exist, so this is a no-op there.
_HOMEBREW_LIB = Path("/opt/homebrew/lib")

_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _derive_title(markdown_path: Path, *, fallback: str) -> str:
    """Use the document's first ``# heading`` as the title, else the filename.

    A non-empty title keeps pandoc from warning on EPUB and gives the produced
    DOCX/EPUB/PDF sensible document metadata.
    """
    try:
        text = markdown_path.read_text(encoding="utf-8")
    except OSError:
        return fallback
    match = _H1.search(text)
    title = match.group(1).strip() if match else ""
    return title or fallback


class MarkdownExportConverter(BaseConverter):
    """Markdown → PDF/DOCX/EPUB via the pandoc binary."""

    supported_extensions = frozenset({".md", ".markdown"})

    DEFAULT_TIMEOUT_SECONDS = 300
    INPUT_FORMAT = "gfm"

    def __init__(
        self,
        target: OutputFormat | str,
        *,
        binary: str | None = None,
        pdf_engine: str = "weasyprint",
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        target = OutputFormat(target)
        if target not in _EXPORT_EXTENSIONS:
            raise ValueError(
                f"{target.value!r} is not an export target; expected one of "
                f"{[f.value for f in _EXPORT_EXTENSIONS]}"
            )
        self._target = target
        self._extension = _EXPORT_EXTENSIONS[target]
        self.name = f"export-{target.value}"
        self._binary = binary or shutil.which("pandoc") or "pandoc"
        self._pdf_engine = pdf_engine
        self._timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------
    # BaseConverter API
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        if shutil.which(self._binary) is None:
            return False
        if self._target is OutputFormat.pdf:
            return shutil.which(self._pdf_engine) is not None
        return True

    def convert(self, input_path: Path, output_dir: Path) -> ConversionResult:
        if not self.supports(input_path):
            raise FormatNotSupportedError(
                f"{self.name} does not support {input_path.suffix!r}; "
                f"expected one of {sorted(self.supported_extensions)}"
            )
        if shutil.which(self._binary) is None:
            raise ConverterUnavailableError(
                "pandoc binary not found — install it (e.g. `brew install pandoc`)."
            )
        if self._target is OutputFormat.pdf and shutil.which(self._pdf_engine) is None:
            raise ConverterUnavailableError(
                f"PDF export needs the {self._pdf_engine!r} engine — install it "
                "(e.g. `brew install weasyprint`)."
            )
        if not input_path.exists() or not input_path.is_file():
            raise ConversionError(f"Input file not found: {input_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        stem = sanitise_filename(input_path.stem)
        output_path = output_dir / f"{uuid.uuid4().hex}_{stem}{self._extension}"
        title = _derive_title(input_path, fallback=stem)

        cmd = [
            self._binary,
            f"--from={self.INPUT_FORMAT}",
            "--standalone",
            "--metadata",
            f"title={title}",
            "--output",
            str(output_path),
            str(input_path),
        ]
        if self._target is OutputFormat.pdf:
            cmd.insert(1, f"--pdf-engine={self._pdf_engine}")

        started = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603 — args are fully controlled
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
                env=self._subprocess_env(),
            )
        except subprocess.TimeoutExpired as exc:
            output_path.unlink(missing_ok=True)
            raise ConversionError(
                f"pandoc timed out after {self._timeout_seconds}s",
                stderr=str(exc),
            ) from exc
        except FileNotFoundError as exc:
            raise ConverterUnavailableError(str(exc)) from exc

        duration = time.monotonic() - started

        if completed.returncode != 0:
            output_path.unlink(missing_ok=True)
            raise ConversionError(
                "pandoc returned a non-zero exit code",
                returncode=completed.returncode,
                stderr=completed.stderr,
            )
        if not output_path.exists() or output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
            raise ConversionError(
                "pandoc exited successfully but produced no output",
                stderr=completed.stderr,
            )

        # Keep pandoc's own warnings ("[WARNING] ...", e.g. a missing image)
        # but drop WeasyPrint's CSS chatter ("WARNING: Ignored ...") about
        # pandoc's default template — it's noise the user can't act on.
        warnings = [
            line
            for line in completed.stderr.splitlines()
            if line.strip() and not line.startswith("WARNING:")
        ]
        return ConversionResult(
            output_path=output_path,
            converter=self.name,
            size_bytes=output_path.stat().st_size,
            duration_seconds=round(duration, 3),
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _subprocess_env(self) -> dict[str, str] | None:
        """Env for the pandoc call; augments the dylib path for WeasyPrint on macOS."""
        if self._target is not OutputFormat.pdf or not _HOMEBREW_LIB.is_dir():
            return None
        env = dict(os.environ)
        existing = env.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        parts = [str(_HOMEBREW_LIB), *([existing] if existing else [])]
        env["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(parts)
        return env
