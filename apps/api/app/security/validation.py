"""Upload validation pipeline (BRIEF §10).

A file passes when:

  1. Its extension is on the configured whitelist;
  2. libmagic's MIME sniff of the first 4 KiB agrees with that extension;
  3. Its size is within ``max_file_size_mb``.

The original filename never reaches disk untouched — callers must use the
``sanitise_filename`` helper from ``app.converters.base`` and prefix with a
UUID. This module focuses on content validation; path traversal is handled
by the storage layer (ticket 9).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import magic

from app.config import get_settings

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class FileValidationError(Exception):
    """Base class for any input rejection."""


class UnsupportedExtensionError(FileValidationError):
    """The file's extension is not on the whitelist."""


class MimeTypeMismatchError(FileValidationError):
    """libmagic disagrees with the extension or the MIME isn't whitelisted."""


class FileTooLargeError(FileValidationError):
    """The file exceeds ``max_file_size_mb``."""


@dataclass(frozen=True, slots=True)
class DetectedFormat:
    """What we know about a file once validation has passed."""

    extension: str          # lower-case, dot-prefixed (e.g. ".pdf")
    mime_type: str          # libmagic mime
    size_bytes: int


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

# Some real-world EPUBs are detected as application/zip (they are zip archives).
# We accept this only when the declared extension is .epub.
_LENIENT_MIME_EQUIVALENCES: dict[str, frozenset[str]] = {
    ".epub": frozenset({"application/epub+zip", "application/zip"}),
    ".docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",  # docx is also a zip archive
        }
    ),
    ".txt": frozenset({"text/plain"}),
    ".html": frozenset({"text/html", "application/xhtml+xml"}),
    ".pdf": frozenset({"application/pdf"}),
    # Markdown input (export direction) — libmagic sniffs it as plain text.
    ".md": frozenset({"text/plain", "text/markdown", "text/x-markdown"}),
    ".markdown": frozenset({"text/plain", "text/markdown", "text/x-markdown"}),
}

_MAGIC = magic.Magic(mime=True)
_SNIFF_BYTES = 4096


def _sniff_mime(input_path: Path) -> str:
    """Return the MIME type as detected by libmagic from the first bytes."""
    with input_path.open("rb") as fh:
        head = fh.read(_SNIFF_BYTES)
    if not head:
        return "application/x-empty"
    return _MAGIC.from_buffer(head).lower()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_format(
    input_path: Path,
    *,
    allowed_extensions: frozenset[str] | None = None,
    allowed_mime_types: frozenset[str] | None = None,
) -> DetectedFormat:
    """Detect a file's format without enforcing size limits.

    Useful for the converter router; size-enforced validation lives in
    :func:`validate_upload`.
    """
    if not input_path.exists() or not input_path.is_file():
        raise FileValidationError(f"file not found: {input_path}")

    settings = get_settings()
    exts = allowed_extensions if allowed_extensions is not None else settings.allowed_extensions_set
    mimes = allowed_mime_types if allowed_mime_types is not None else settings.allowed_mime_types_set

    ext = input_path.suffix.lower()
    if ext not in exts:
        raise UnsupportedExtensionError(
            f"extension {ext!r} is not allowed; expected one of {sorted(exts)}"
        )

    mime = _sniff_mime(input_path)
    accepted_for_ext = _LENIENT_MIME_EQUIVALENCES.get(ext, frozenset({mime}))
    if mime not in accepted_for_ext or not (accepted_for_ext & mimes or mime in mimes):
        raise MimeTypeMismatchError(
            f"libmagic detected {mime!r} which is incompatible with extension {ext!r}"
        )

    size_bytes = input_path.stat().st_size
    return DetectedFormat(extension=ext, mime_type=mime, size_bytes=size_bytes)


def validate_upload(
    input_path: Path,
    *,
    max_file_size_mb: int | None = None,
    allowed_extensions: frozenset[str] | None = None,
    allowed_mime_types: frozenset[str] | None = None,
) -> DetectedFormat:
    """Full upload check: extension + MIME + size."""
    settings = get_settings()
    detected = detect_format(
        input_path,
        allowed_extensions=allowed_extensions,
        allowed_mime_types=allowed_mime_types,
    )

    limit_mb = max_file_size_mb if max_file_size_mb is not None else settings.max_file_size_mb
    limit_bytes = limit_mb * 1024 * 1024
    if detected.size_bytes > limit_bytes:
        raise FileTooLargeError(
            f"file is {detected.size_bytes} bytes; limit is {limit_bytes} ({limit_mb} MB)"
        )

    return detected


def validate_markdown_input(
    input_path: Path,
    *,
    max_file_size_mb: int | None = None,
) -> DetectedFormat:
    """Validate a markdown upload for the export direction (markdown → X).

    Same extension/MIME/size pipeline as :func:`validate_upload`, but against
    the markdown-input whitelist (``.md``/``.markdown``) instead of the
    document whitelist used when importing *to* markdown.
    """
    settings = get_settings()
    return validate_upload(
        input_path,
        max_file_size_mb=max_file_size_mb,
        allowed_extensions=settings.export_input_extensions_set,
        allowed_mime_types=settings.export_input_mime_types_set,
    )
