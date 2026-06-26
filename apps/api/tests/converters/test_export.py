"""Unit tests for MarkdownExportConverter (markdown → PDF/DOCX/EPUB)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.converters import MarkdownExportConverter, OutputFormat
from app.converters.errors import (
    ConverterUnavailableError,
    FormatNotSupportedError,
)


def test_name_and_supported_extensions() -> None:
    converter = MarkdownExportConverter(OutputFormat.docx)
    assert converter.name == "export-docx"
    assert converter.supports(Path("rapport.md"))
    assert converter.supports(Path("RAPPORT.MARKDOWN"))
    assert not converter.supports(Path("rapport.pdf"))
    assert not converter.supports(Path("book.epub"))


def test_markdown_is_not_an_export_target() -> None:
    # 'markdown' is the import/no-op direction — it can't be an export target.
    with pytest.raises(ValueError, match="markdown"):
        MarkdownExportConverter(OutputFormat.markdown)


def test_rejects_non_markdown_input(tmp_path: Path) -> None:
    converter = MarkdownExportConverter(OutputFormat.pdf)
    pdf = tmp_path / "fake.pdf"
    pdf.touch()
    with pytest.raises(FormatNotSupportedError):
        converter.convert(pdf, tmp_path / "out")


def test_unavailable_binary_raises(tmp_path: Path, markdown_file: Path) -> None:
    converter = MarkdownExportConverter(
        OutputFormat.docx, binary="/nonexistent/pandoc-bin"
    )
    assert converter.is_available() is False
    with pytest.raises(ConverterUnavailableError):
        converter.convert(markdown_file, tmp_path / "out")


def test_pdf_unavailable_when_engine_missing(
    tmp_path: Path, markdown_file: Path
) -> None:
    # pandoc may exist, but a missing PDF engine must surface as unavailable,
    # not as a cryptic conversion failure.
    converter = MarkdownExportConverter(
        OutputFormat.pdf, pdf_engine="/nonexistent/weasyprint"
    )
    assert converter.is_available() is False
    with pytest.raises(ConverterUnavailableError):
        converter.convert(markdown_file, tmp_path / "out")


@pytest.mark.usefixtures("skip_if_no_pandoc")
def test_converts_markdown_to_docx(markdown_file: Path, output_dir: Path) -> None:
    converter = MarkdownExportConverter(OutputFormat.docx)
    result = converter.convert(markdown_file, output_dir)

    assert result.converter == "export-docx"
    assert result.output_path.exists()
    assert result.output_path.suffix == ".docx"
    assert result.size_bytes > 0
    # .docx is an OOXML zip — magic bytes "PK".
    assert result.output_path.read_bytes()[:2] == b"PK"


@pytest.mark.usefixtures("skip_if_no_pandoc")
def test_converts_markdown_to_epub(markdown_file: Path, output_dir: Path) -> None:
    converter = MarkdownExportConverter(OutputFormat.epub)
    result = converter.convert(markdown_file, output_dir)

    assert result.converter == "export-epub"
    assert result.output_path.exists()
    assert result.output_path.suffix == ".epub"
    assert result.size_bytes > 0
    assert result.output_path.read_bytes()[:2] == b"PK"


@pytest.mark.usefixtures("skip_if_no_pandoc", "skip_if_no_weasyprint")
def test_converts_markdown_to_pdf(markdown_file: Path, output_dir: Path) -> None:
    converter = MarkdownExportConverter(OutputFormat.pdf)
    result = converter.convert(markdown_file, output_dir)

    assert result.converter == "export-pdf"
    assert result.output_path.exists()
    assert result.output_path.suffix == ".pdf"
    assert result.size_bytes > 0
    # Every PDF starts with the "%PDF" signature.
    assert result.output_path.read_bytes()[:4] == b"%PDF"
    # WeasyPrint chatters about CSS properties in pandoc's default template
    # ("WARNING: Ignored ...") — pure noise the user can't act on. It must not
    # leak into the surfaced warnings.
    assert all(not w.startswith("WARNING:") for w in result.warnings)
