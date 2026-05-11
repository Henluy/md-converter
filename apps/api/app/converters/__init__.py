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
from app.converters.pandoc import PandocConverter
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
    "PandocConverter",
    "RoutingDecision",
    "TargetFormat",
    "build_default_registry",
]


def build_default_registry() -> dict[str, BaseConverter]:
    """Registry of converters available today.

    Tickets 8 will plug pymupdf/marker/markitdown instances in here.
    The router gracefully reports "not supported" for missing entries.
    """
    return {
        "pandoc": PandocConverter(),
    }
