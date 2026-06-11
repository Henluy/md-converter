"""The conversion task retries transient infra errors, not bad input."""

from __future__ import annotations

from sqlalchemy.exc import OperationalError

from app.converters import (
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
)
from app.tasks.conversion import MAX_RETRIES, RETRYABLE_ERRORS, convert_file_task


def test_transient_db_errors_are_retryable() -> None:
    assert issubclass(OperationalError, RETRYABLE_ERRORS)


def test_deterministic_conversion_errors_are_not_retryable() -> None:
    for exc in (ConversionError, ConverterUnavailableError, FormatNotSupportedError):
        assert not issubclass(exc, RETRYABLE_ERRORS), (
            f"{exc.__name__} is deterministic — retrying it wastes work"
        )


def test_task_has_bounded_retries() -> None:
    assert MAX_RETRIES >= 1
    assert convert_file_task.max_retries == MAX_RETRIES
