"""Tests for ConverterRouter — routing decisions and override behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.converters import (
    ConverterRouter,
    FormatNotSupportedError,
    MarkItDownConverter,
    OcrPdfConverter,
    PandocConverter,
    PymuPdfConverter,
    TargetFormat,
    build_default_registry,
)
from app.security import UnsupportedExtensionError


def _make(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_router_routes_epub_to_pandoc(epub_file: Path) -> None:
    router = ConverterRouter(build_default_registry())
    decision = router.resolve(epub_file)

    assert decision.target_format == TargetFormat.epub
    assert decision.converter_name == "pandoc"
    assert isinstance(decision.converter, PandocConverter)


def test_router_routes_text_pdf_to_pymupdf(text_pdf: Path) -> None:
    router = ConverterRouter(build_default_registry())
    decision = router.resolve(text_pdf)

    assert decision.target_format == TargetFormat.pdf_native
    assert decision.converter_name == "pymupdf"
    assert isinstance(decision.converter, PymuPdfConverter)


def test_router_routes_scanned_pdf_to_ocr(scanned_pdf: Path) -> None:
    """Scanned PDFs route to the (opt-in) OCR converter."""
    router = ConverterRouter(build_default_registry())
    decision = router.resolve(scanned_pdf)

    assert decision.target_format == TargetFormat.pdf_scanned
    assert decision.converter_name == "ocr"
    assert isinstance(decision.converter, OcrPdfConverter)


def test_router_routes_docx_to_markitdown(docx_file: Path) -> None:
    router = ConverterRouter(build_default_registry())
    decision = router.resolve(docx_file)

    assert decision.target_format == TargetFormat.docx
    assert decision.converter_name == "markitdown"
    assert isinstance(decision.converter, MarkItDownConverter)


def test_router_routes_html_to_markitdown(html_file: Path) -> None:
    router = ConverterRouter(build_default_registry())
    decision = router.resolve(html_file)

    assert decision.target_format == TargetFormat.html
    assert decision.converter_name == "markitdown"


def test_router_routes_txt_to_markitdown(txt_file: Path) -> None:
    router = ConverterRouter(build_default_registry())
    decision = router.resolve(txt_file)

    assert decision.target_format == TargetFormat.txt
    assert decision.converter_name == "markitdown"


def test_router_override_with_unsupported_converter_raises(epub_file: Path) -> None:
    """Forcing a converter that doesn't handle .epub must fail loudly."""
    router = ConverterRouter({"pandoc": PandocConverter()})

    with pytest.raises(FormatNotSupportedError) as excinfo:
        router.resolve(epub_file, override="ghostwriter")

    assert "ghostwriter" in str(excinfo.value)


def test_router_rejects_unknown_extension(tmp_path: Path) -> None:
    weird = _make(tmp_path / "doc.xyz", b"hello")
    router = ConverterRouter(build_default_registry())

    with pytest.raises(UnsupportedExtensionError):
        router.resolve(weird)


def test_router_exposes_available_converters() -> None:
    router = ConverterRouter(build_default_registry())
    assert router.available_converters == [
        "export-docx",
        "export-epub",
        "export-pdf",
        "markitdown",
        "ocr",
        "pandoc",
        "pymupdf",
    ]
