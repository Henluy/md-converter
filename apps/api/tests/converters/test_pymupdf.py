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


def _build_pdf_with_image(path: Path) -> Path:
    """A text PDF that also embeds a sizeable raster image."""
    import pymupdf

    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 240, 320))
    pix.set_rect(pix.irect, (10, 120, 220))  # solid fill so it's a real image
    body = "The quick brown fox jumps over the lazy dog. " * 3
    with pymupdf.open() as doc:
        page = doc.new_page()
        for i in range(30):
            page.insert_text((72, 80 + i * 14), body, fontsize=11)
        page.insert_image(pymupdf.Rect(300, 360, 540, 680), pixmap=pix)
        doc.save(str(path))
    return path


def test_extracts_embedded_images_to_media_dir(
    tmp_path: Path, output_dir: Path
) -> None:
    """Text-native PDFs must keep their images — extracted to a flat media/
    folder and referenced from the markdown (parity with the EPUB path)."""
    pdf = _build_pdf_with_image(tmp_path / "with_image.pdf")
    converter = PymuPdfConverter()
    result = converter.convert(pdf, output_dir)

    md = result.output_path.read_text(encoding="utf-8")
    media_dir = output_dir / "media"
    assert media_dir.is_dir(), "images should be extracted to a media/ folder"
    assert any(media_dir.iterdir()), "media/ should contain at least one image"
    assert "media/" in md, "markdown should reference the extracted images"
