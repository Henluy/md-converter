"""Tests for PymuPdfConverter."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.converters import PymuPdfConverter
from app.converters.errors import ConversionError, FormatNotSupportedError


def test_supports_pdf_only() -> None:
    converter = PymuPdfConverter()
    assert converter.supports(Path("doc.pdf"))
    assert not converter.supports(Path("doc.epub"))


def test_converts_text_pdf_to_markdown(text_pdf: Path, output_dir: Path) -> None:
    converter = PymuPdfConverter()
    result = converter.convert(text_pdf, output_dir)

    assert result.converter == "pymupdf"
    assert result.output_path.exists()
    assert result.size_bytes > 0
    assert result.pages == 1
    md = result.output_path.read_text(encoding="utf-8")
    assert "Hello md-converter" in md


def test_unsupported_format_raises(tmp_path: Path) -> None:
    converter = PymuPdfConverter()
    bogus = tmp_path / "x.epub"
    bogus.touch()
    with pytest.raises(FormatNotSupportedError):
        converter.convert(bogus, tmp_path / "out")


def test_missing_input_raises(tmp_path: Path) -> None:
    converter = PymuPdfConverter()
    with pytest.raises(ConversionError):
        converter.convert(tmp_path / "missing.pdf", tmp_path / "out")


def test_image_only_pdf_returns_empty_markdown(
    scanned_pdf: Path, output_dir: Path
) -> None:
    """A PDF with no extractable text → pymupdf4llm yields nothing."""
    converter = PymuPdfConverter()
    with pytest.raises(ConversionError):
        converter.convert(scanned_pdf, output_dir)
