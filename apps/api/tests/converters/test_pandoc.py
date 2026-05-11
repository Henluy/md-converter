"""Unit tests for PandocConverter."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.converters import PandocConverter
from app.converters.base import sanitise_filename
from app.converters.errors import (
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
)


def test_supports_epub_only() -> None:
    converter = PandocConverter()
    assert converter.supports(Path("book.epub"))
    assert converter.supports(Path("BOOK.EPUB"))
    assert not converter.supports(Path("book.pdf"))
    assert not converter.supports(Path("book.docx"))


def test_sanitise_filename_strips_traversal_and_unsafe_chars() -> None:
    assert sanitise_filename("../../etc/passwd") == "passwd"
    assert sanitise_filename("My Book Title?.pdf") == "My_Book_Title_.pdf"
    assert sanitise_filename("") == "file"


def test_unsupported_format_raises(tmp_path: Path) -> None:
    converter = PandocConverter()
    pdf = tmp_path / "fake.pdf"
    pdf.touch()
    with pytest.raises(FormatNotSupportedError):
        converter.convert(pdf, tmp_path / "out")


def test_unavailable_binary_raises(tmp_path: Path, epub_file: Path) -> None:
    converter = PandocConverter(binary="/nonexistent/pandoc-bin")
    with pytest.raises(ConverterUnavailableError):
        converter.convert(epub_file, tmp_path / "out")


def test_failing_binary_surfaces_returncode(
    tmp_path: Path,
    epub_file: Path,
    fake_failing_pandoc: Path,
) -> None:
    converter = PandocConverter(binary=str(fake_failing_pandoc))
    with pytest.raises(ConversionError) as excinfo:
        converter.convert(epub_file, tmp_path / "out")
    assert excinfo.value.returncode == 5
    assert "boom" in (excinfo.value.stderr or "")


@pytest.mark.usefixtures("skip_if_no_pandoc")
def test_converts_epub_to_markdown(
    epub_file: Path,
    output_dir: Path,
) -> None:
    converter = PandocConverter()
    result = converter.convert(epub_file, output_dir)

    assert result.converter == "pandoc"
    assert result.output_path.exists()
    assert result.output_path.suffix == ".md"
    assert result.size_bytes > 0
    assert result.duration_seconds >= 0.0

    md = result.output_path.read_text(encoding="utf-8")
    # Structure preserved: heading, list and bold/italic from the source EPUB.
    assert "Chapter One" in md
    assert "First bullet" in md
    assert "**bold**" in md
    assert "*italics*" in md
