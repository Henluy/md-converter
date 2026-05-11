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
from app.converters.markitdown import MarkItDownConverter
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
    "PandocConverter",
    "PymuPdfConverter",
    "RoutingDecision",
    "TargetFormat",
    "build_default_registry",
]


def build_default_registry() -> dict[str, BaseConverter]:
    """Registry of converters available today.

    Ticket 8b will plug ``marker`` (OCR for scanned PDFs) in once we have a
    sane lazy-loading strategy for its ML weights. Router resolves to it
    by name and surfaces a clear ``FormatNotSupportedError`` until then.
    """
    return {
        "pandoc": PandocConverter(),
        "pymupdf": PymuPdfConverter(),
        "markitdown": MarkItDownConverter(),
    }
