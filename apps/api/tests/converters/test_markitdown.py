"""Tests for MarkItDownConverter."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.converters import MarkItDownConverter
from app.converters.errors import ConversionError, FormatNotSupportedError


def test_supports_docx_html_txt() -> None:
    converter = MarkItDownConverter()
    for ext in (".docx", ".html", ".txt"):
        assert converter.supports(Path(f"x{ext}"))
    assert not converter.supports(Path("x.pdf"))


def test_converts_html(html_file: Path, output_dir: Path) -> None:
    converter = MarkItDownConverter()
    result = converter.convert(html_file, output_dir)

    assert result.converter == "markitdown"
    md = result.output_path.read_text(encoding="utf-8")
    assert "Hello" in md
    assert "md-converter" in md


def test_converts_txt(txt_file: Path, output_dir: Path) -> None:
    converter = MarkItDownConverter()
    result = converter.convert(txt_file, output_dir)
    md = result.output_path.read_text(encoding="utf-8")
    assert "plain text file" in md


def test_converts_docx(docx_file: Path, output_dir: Path) -> None:
    converter = MarkItDownConverter()
    result = converter.convert(docx_file, output_dir)
    md = result.output_path.read_text(encoding="utf-8")
    assert "Hello from docx" in md


def test_unsupported_format_raises(tmp_path: Path) -> None:
    converter = MarkItDownConverter()
    bogus = tmp_path / "x.pdf"
    bogus.touch()
    with pytest.raises(FormatNotSupportedError):
        converter.convert(bogus, tmp_path / "out")


def test_missing_input_raises(tmp_path: Path) -> None:
    converter = MarkItDownConverter()
    with pytest.raises(ConversionError):
        converter.convert(tmp_path / "missing.txt", tmp_path / "out")
