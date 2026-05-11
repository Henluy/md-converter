"""Converter exception hierarchy."""

from __future__ import annotations


class ConverterError(Exception):
    """Base class for all converter failures."""


class ConverterUnavailableError(ConverterError):
    """The required binary or library is missing on this host."""


class FormatNotSupportedError(ConverterError):
    """The input format is outside this converter's whitelist."""


class ConversionError(ConverterError):
    """Conversion attempted but the underlying tool returned a failure."""

    def __init__(self, message: str, *, returncode: int | None = None, stderr: str | None = None) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr
