"""Converter strategies (Strategy pattern over BaseConverter).

Each converter takes an input file path and returns a ConversionResult.
Routing (which converter handles which format) lives in router.py (ticket 7).
"""

from app.converters.base import BaseConverter, ConversionResult
from app.converters.errors import (
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
)
from app.converters.pandoc import PandocConverter

__all__ = [
    "BaseConverter",
    "ConversionError",
    "ConversionResult",
    "ConverterUnavailableError",
    "FormatNotSupportedError",
    "PandocConverter",
]
