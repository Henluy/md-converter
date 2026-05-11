"""Celery task tests in eager mode (no broker, synchronous execution).

Shared fixtures (``epub_file``, ``output_dir``, ``skip_if_no_pandoc``)
come from the root ``tests/conftest.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.converters.errors import (
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
)
from app.tasks import convert_file_task


@pytest.mark.usefixtures("skip_if_no_pandoc")
def test_task_runs_eagerly_and_produces_markdown(
    epub_file: Path,
    output_dir: Path,
) -> None:
    """Eager mode → task executes synchronously in-process."""
    async_result = convert_file_task.apply(
        kwargs={
            "input_path": str(epub_file),
            "output_dir": str(output_dir),
            "converter_name": "pandoc",
        }
    )

    assert async_result.successful()
    payload = async_result.result

    assert payload["converter"] == "pandoc"
    assert payload["size_bytes"] > 0
    output_path = Path(payload["output_path"])
    assert output_path.exists()
    assert output_path.suffix == ".md"
    assert "Chapter One" in output_path.read_text(encoding="utf-8")


def test_unknown_converter_raises(tmp_path: Path, epub_file: Path) -> None:
    """An unknown converter name bubbles up as ConverterUnavailableError.

    Eager mode with ``task_eager_propagates=True`` re-raises directly from
    ``.apply()`` — that matches how worker failures surface in production
    once translated into job/file row updates (ticket 10).
    """
    with pytest.raises(ConverterUnavailableError):
        convert_file_task.apply(
            kwargs={
                "input_path": str(epub_file),
                "output_dir": str(tmp_path / "out"),
                "converter_name": "ghostwriter",
            }
        )


def test_unsupported_format_raises(tmp_path: Path) -> None:
    """Pandoc rejects a PDF → FormatNotSupportedError propagates."""
    pdf = tmp_path / "fake.pdf"
    pdf.touch()
    with pytest.raises(FormatNotSupportedError):
        convert_file_task.apply(
            kwargs={
                "input_path": str(pdf),
                "output_dir": str(tmp_path / "out"),
                "converter_name": "pandoc",
            }
        )


def test_missing_input_raises(tmp_path: Path) -> None:
    """A non-existent file triggers ConversionError."""
    with pytest.raises(ConversionError):
        convert_file_task.apply(
            kwargs={
                "input_path": str(tmp_path / "missing.epub"),
                "output_dir": str(tmp_path / "out"),
                "converter_name": "pandoc",
            }
        )
