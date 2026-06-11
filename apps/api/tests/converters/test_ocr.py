"""Tests for the opt-in OCR converter (scanned PDFs)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.converters.errors import (
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
)
from app.converters.ocr import OcrPdfConverter


def test_supports_pdf_only() -> None:
    converter = OcrPdfConverter(enabled=True)
    assert converter.supports(Path("doc.pdf"))
    assert not converter.supports(Path("doc.epub"))


def test_disabled_converter_is_unavailable() -> None:
    assert OcrPdfConverter(enabled=False).is_available() is False


def test_disabled_convert_raises_unavailable(
    scanned_pdf: Path, output_dir: Path
) -> None:
    converter = OcrPdfConverter(enabled=False)
    with pytest.raises(ConverterUnavailableError, match="disabled"):
        converter.convert(scanned_pdf, output_dir)


def test_enabled_but_binary_missing_raises_unavailable(
    scanned_pdf: Path, output_dir: Path
) -> None:
    converter = OcrPdfConverter(enabled=True, binary="md-converter-no-such-ocr-bin")
    with pytest.raises(ConverterUnavailableError):
        converter.convert(scanned_pdf, output_dir)


def test_unsupported_format_raises(tmp_path: Path) -> None:
    converter = OcrPdfConverter(enabled=True)
    bogus = tmp_path / "x.epub"
    bogus.touch()
    with pytest.raises(FormatNotSupportedError):
        converter.convert(bogus, tmp_path / "out")


def test_missing_input_raises(tmp_path: Path) -> None:
    converter = OcrPdfConverter(enabled=True, binary=shutil.which("echo") or "echo")
    with pytest.raises(ConversionError):
        converter.convert(tmp_path / "missing.pdf", tmp_path / "out")


def _build_rasterized_text_pdf(path: Path) -> Path:
    """An image-only PDF page that *visually* contains text (OCR target)."""
    import pymupdf

    src = pymupdf.open()
    page = src.new_page(width=612, height=792)
    page.insert_text((72, 200), "OCR CONVERTER TEST", fontsize=40)
    page.insert_text((72, 320), "the quick brown fox", fontsize=40)
    pix = page.get_pixmap(dpi=150)
    src.close()

    out = pymupdf.open()
    opage = out.new_page(width=612, height=792)
    opage.insert_image(opage.rect, pixmap=pix)
    out.save(str(path))
    out.close()
    return path


@pytest.mark.skipif(
    shutil.which("ocrmypdf") is None, reason="ocrmypdf not installed on this host"
)
def test_real_ocr_produces_markdown(tmp_path: Path, output_dir: Path) -> None:
    pdf = _build_rasterized_text_pdf(tmp_path / "scanned.pdf")
    converter = OcrPdfConverter(enabled=True)

    result = converter.convert(pdf, output_dir)

    assert result.converter == "ocr"
    assert result.output_path.exists()
    assert result.size_bytes > 0
