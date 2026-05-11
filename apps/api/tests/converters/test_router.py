"""Tests for ConverterRouter — routing decisions and override behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.converters import (
    ConverterRouter,
    FormatNotSupportedError,
    PandocConverter,
    TargetFormat,
    build_default_registry,
)
from app.security import UnsupportedExtensionError

_PDF_BYTES = b"%PDF-1.7\n1 0 obj <<>> endobj\n%%EOF\n"


def _make(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_router_routes_epub_to_pandoc(epub_file: Path) -> None:
    router = ConverterRouter(build_default_registry())
    decision = router.resolve(epub_file)

    assert decision.target_format == TargetFormat.epub
    assert decision.converter_name == "pandoc"
    assert isinstance(decision.converter, PandocConverter)


def test_router_text_native_pdf_target_but_no_converter(tmp_path: Path) -> None:
    """Today only pandoc is registered → PDF target raises FormatNotSupportedError."""
    pdf = _make(tmp_path / "doc.pdf", _PDF_BYTES)
    router = ConverterRouter(build_default_registry())

    with pytest.raises(FormatNotSupportedError) as excinfo:
        router.resolve(pdf)

    assert "pymupdf" in str(excinfo.value)


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
    assert router.available_converters == ["pandoc"]
