"""Tests for the upload-validation pipeline (extension + magic + size)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.security import (
    FileTooLargeError,
    FileValidationError,
    MimeTypeMismatchError,
    UnsupportedExtensionError,
    detect_format,
    validate_markdown_input,
    validate_upload,
)

# Minimal PDF that libmagic recognises as application/pdf.
_PDF_BYTES = b"%PDF-1.7\n1 0 obj <<>> endobj\n%%EOF\n"


def _make_file(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_detect_epub_accepts_minimal_archive(epub_file: Path) -> None:
    detected = detect_format(epub_file)
    assert detected.extension == ".epub"
    assert detected.mime_type in {"application/epub+zip", "application/zip"}
    assert detected.size_bytes > 0


def test_detect_pdf_accepts_native_pdf(tmp_path: Path) -> None:
    pdf = _make_file(tmp_path / "doc.pdf", _PDF_BYTES)
    detected = detect_format(pdf)
    assert detected.extension == ".pdf"
    assert detected.mime_type == "application/pdf"


def test_detect_rejects_unknown_extension(tmp_path: Path) -> None:
    weird = _make_file(tmp_path / "doc.xyz", b"hello")
    with pytest.raises(UnsupportedExtensionError):
        detect_format(weird)


def test_detect_rejects_wrong_magic(tmp_path: Path) -> None:
    """A file claiming .pdf but actually plain text is rejected."""
    spoofed = _make_file(tmp_path / "evil.pdf", b"just plain text, not a pdf")
    with pytest.raises(MimeTypeMismatchError):
        detect_format(spoofed)


def test_detect_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError):
        detect_format(tmp_path / "missing.pdf")


def test_validate_enforces_size_limit(tmp_path: Path) -> None:
    pdf = _make_file(tmp_path / "doc.pdf", _PDF_BYTES + b"\x00" * 2048)
    # Pass tiny limit (1 byte expressed as MB → 0 MB effectively).
    with pytest.raises(FileTooLargeError):
        validate_upload(pdf, max_file_size_mb=0)


def test_validate_passes_within_limit(tmp_path: Path) -> None:
    pdf = _make_file(tmp_path / "doc.pdf", _PDF_BYTES)
    detected = validate_upload(pdf, max_file_size_mb=10)
    assert detected.extension == ".pdf"


# --- Markdown input (export direction: markdown → PDF/DOCX/EPUB) -----------


def test_validate_markdown_input_accepts_md(markdown_file: Path) -> None:
    detected = validate_markdown_input(markdown_file)
    assert detected.extension == ".md"
    assert detected.mime_type == "text/plain"


def test_validate_markdown_input_accepts_markdown_extension(tmp_path: Path) -> None:
    doc = _make_file(tmp_path / "note.markdown", b"# Title\n\nbody\n")
    detected = validate_markdown_input(doc)
    assert detected.extension == ".markdown"


def test_validate_markdown_input_rejects_documents(tmp_path: Path) -> None:
    pdf = _make_file(tmp_path / "doc.pdf", _PDF_BYTES)
    with pytest.raises(UnsupportedExtensionError):
        validate_markdown_input(pdf)


def test_default_upload_rejects_markdown(markdown_file: Path) -> None:
    # The import path (document → markdown) must NOT accept a .md upload.
    with pytest.raises(UnsupportedExtensionError):
        validate_upload(markdown_file)
