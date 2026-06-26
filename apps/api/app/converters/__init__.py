"""Converter strategies (Strategy pattern over BaseConverter).

Each converter takes an input file path and returns a ConversionResult.
Routing (which converter handles which format) lives in router.py.
"""

from app.converters.base import BaseConverter, ConversionResult
from app.converters.errors import (
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
)
from app.converters.export import MarkdownExportConverter, OutputFormat
from app.converters.markitdown import MarkItDownConverter
from app.converters.ocr import OcrPdfConverter
from app.converters.pandoc import PandocConverter
from app.converters.pymupdf_converter import PymuPdfConverter
from app.converters.router import (
    DEFAULT_BY_FORMAT,
    ConverterRouter,
    RoutingDecision,
    TargetFormat,
)

__all__ = [
    "DEFAULT_BY_FORMAT",
    "BaseConverter",
    "ConversionError",
    "ConversionResult",
    "ConverterRouter",
    "ConverterUnavailableError",
    "FormatNotSupportedError",
    "MarkItDownConverter",
    "MarkdownExportConverter",
    "OcrPdfConverter",
    "OutputFormat",
    "PandocConverter",
    "PymuPdfConverter",
    "RoutingDecision",
    "TargetFormat",
    "build_default_registry",
]


def build_default_registry() -> dict[str, BaseConverter]:
    """Registry of converters available today.

    The OCR converter is always registered so scanned PDFs route to it, but
    it stays inert (raising a clear ``ConverterUnavailableError``) unless
    ``ENABLE_OCR=1`` and the ocrmypdf binary is present.
    """
    from app.config import get_settings

    settings = get_settings()
    return {
        "pandoc": PandocConverter(),
        "pymupdf": PymuPdfConverter(),
        "markitdown": MarkItDownConverter(),
        "ocr": OcrPdfConverter(
            enabled=settings.enable_ocr, language=settings.ocr_language
        ),
        # Reverse direction: markdown → PDF/DOCX/EPUB. Selected by a job's
        # target_format, not by input-format routing.
        "export-pdf": MarkdownExportConverter(
            OutputFormat.pdf, pdf_engine=settings.export_pdf_engine
        ),
        "export-docx": MarkdownExportConverter(OutputFormat.docx),
        "export-epub": MarkdownExportConverter(OutputFormat.epub),
    }
