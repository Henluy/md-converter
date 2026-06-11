"""Tests for the converter wall-clock timeout helper."""

from __future__ import annotations

import time

import pytest

from app.converters.base import ConverterTimeoutError, run_with_timeout


def test_returns_value_when_fast() -> None:
    assert run_with_timeout(lambda: 42, seconds=5) == 42


def test_raises_when_slower_than_budget() -> None:
    with pytest.raises(ConverterTimeoutError):
        run_with_timeout(lambda: time.sleep(2), seconds=0.2)


def test_propagates_inner_exception() -> None:
    def boom() -> None:
        raise ValueError("inner")

    with pytest.raises(ValueError, match="inner"):
        run_with_timeout(boom, seconds=5)
