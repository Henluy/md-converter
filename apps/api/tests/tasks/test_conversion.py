"""Celery task tests in eager mode (no broker, synchronous execution).

Shared fixtures (``epub_file``, ``output_dir``, ``skip_if_no_pandoc``)
come from the root ``tests/conftest.py``. The task now routes via
``validate_upload → ConverterRouter`` before invoking the converter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.converters import FormatNotSupportedError
from app.security import (
    FileValidationError,
    MimeTypeMismatchError,
    UnsupportedExtensionError,
)
from app.tasks import convert_file_task

_PDF_BYTES = b"%PDF-1.7\n1 0 obj <<>> endobj\n%%EOF\n"


@pytest.mark.usefixtures("skip_if_no_pandoc")
def test_task_routes_epub_to_pandoc_and_returns_payload(
    epub_file: Path,
    output_dir: Path,
) -> None:
    """Eager mode → task executes synchronously in-process."""
    async_result = convert_file_task.apply(
        kwargs={
            "input_path": str(epub_file),
            "output_dir": str(output_dir),
        }
    )

    assert async_result.successful()
    payload = async_result.result

    assert payload["converter"] == "pandoc"
    assert payload["target_format"] == "epub"
    assert payload["detected_mime"] in {"application/epub+zip", "application/zip"}
    assert payload["size_bytes"] > 0

    output_path = Path(payload["output_path"])
    assert output_path.exists()
    assert "Chapter One" in output_path.read_text(encoding="utf-8")


def test_unknown_override_raises_format_not_supported(
    tmp_path: Path,
    epub_file: Path,
) -> None:
    """An unknown converter override surfaces as FormatNotSupportedError."""
    with pytest.raises(FormatNotSupportedError):
        convert_file_task.apply(
            kwargs={
                "input_path": str(epub_file),
                "output_dir": str(tmp_path / "out"),
                "override": "ghostwriter",
            }
        )


def test_disallowed_extension_is_rejected(tmp_path: Path) -> None:
    """Validation runs before routing — unsupported extension → UnsupportedExtensionError."""
    weird = tmp_path / "doc.xyz"
    weird.write_bytes(b"hello")
    with pytest.raises(UnsupportedExtensionError):
        convert_file_task.apply(
            kwargs={
                "input_path": str(weird),
                "output_dir": str(tmp_path / "out"),
            }
        )


def test_spoofed_extension_is_rejected(tmp_path: Path) -> None:
    """Plain text saved with .pdf extension → MimeTypeMismatchError."""
    spoof = tmp_path / "fake.pdf"
    spoof.write_bytes(b"not a real pdf, just text")
    with pytest.raises(MimeTypeMismatchError):
        convert_file_task.apply(
            kwargs={
                "input_path": str(spoof),
                "output_dir": str(tmp_path / "out"),
            }
        )


def test_native_pdf_has_no_converter_yet(tmp_path: Path) -> None:
    """Ticket 7 routes PDFs to pymupdf; ticket 8 will register it."""
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(_PDF_BYTES)
    with pytest.raises(FormatNotSupportedError):
        convert_file_task.apply(
            kwargs={
                "input_path": str(pdf),
                "output_dir": str(tmp_path / "out"),
            }
        )


def test_missing_input_raises_validation_error(tmp_path: Path) -> None:
    """A non-existent file is caught by validation, not by the converter."""
    with pytest.raises(FileValidationError):
        convert_file_task.apply(
            kwargs={
                "input_path": str(tmp_path / "missing.epub"),
                "output_dir": str(tmp_path / "out"),
            }
        )
