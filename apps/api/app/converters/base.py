"""Strategy interface for all document → markdown converters.

Every converter sub-class:
- declares which file extensions it supports (lower-case, dot-prefixed),
- implements ``convert(input_path, output_dir)`` returning a ``ConversionResult``.

Routing/format-detection lives in ``router.py`` (ticket 7). Each converter
remains self-contained and unaware of the others, so we can compose or
swap them freely.
"""

from __future__ import annotations

import concurrent.futures
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from app.processors import clean_markdown

_T = TypeVar("_T")


class ConverterTimeoutError(Exception):
    """Raised when a converter exceeds its wall-clock budget."""


def run_with_timeout(fn: Callable[[], _T], *, seconds: float) -> _T:
    """Run ``fn`` on a worker thread, raising ConverterTimeoutError past ``seconds``.

    Libraries like MarkItDown expose only a blocking, synchronous API. We
    can't kill the underlying call (it may be in C), but we *can* stop
    waiting on it so the worker fails fast with a clear error instead of
    hanging until Celery's blunt soft time limit fires. The orphaned thread
    is left to finish on its own; workers recycle after a bounded number of
    tasks.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        result = future.result(timeout=seconds)
    except concurrent.futures.TimeoutError as exc:
        executor.shutdown(wait=False, cancel_futures=True)
        raise ConverterTimeoutError(f"operation exceeded {seconds}s") from exc
    executor.shutdown(wait=False)
    return result

# Whitelist of "safe" output filename characters. Conservative on purpose:
# anything outside [a-zA-Z0-9._-] becomes "_". The original filename is kept
# in the DB; on disk we use this sanitised form prefixed by a UUID so two
# different uploads can't collide or escape /data.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitise_filename(name: str, *, max_length: int = 200) -> str:
    """Return a filesystem-safe filename (no path components, no traversal)."""
    base = Path(name).name  # strip any directories the caller passed in
    safe = _UNSAFE.sub("_", base).strip("._-") or "file"
    return safe[:max_length]


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """Outcome of a successful conversion."""

    output_path: Path
    converter: str
    pages: int | None = None
    size_bytes: int = 0
    duration_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)


class BaseConverter(ABC):
    """Abstract converter — implement `name`, `supported_extensions`, `convert`."""

    #: Human-readable identifier, stored in `files.converter_used`.
    name: str

    #: Lower-case, dot-prefixed extensions this converter handles (e.g. {".epub"}).
    supported_extensions: frozenset[str]

    def supports(self, input_path: Path) -> bool:
        return input_path.suffix.lower() in self.supported_extensions

    @abstractmethod
    def convert(self, input_path: Path, output_dir: Path) -> ConversionResult:
        """Convert ``input_path`` and return the path to the produced .md."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """True iff the required system binary / library is on this host."""
        raise NotImplementedError


def write_cleaned_markdown(
    output_path: Path,
    raw_text: str,
    *,
    media_dir: Path | None = None,
) -> None:
    """Clean ``raw_text`` and write it to ``output_path``.

    If the cleaner asks us to rename the media folder (it always does so
    when the converter scattered images under ``…_media/``) and the caller
    passed a ``media_dir`` that still exists, we rename it to the flat
    ``media`` form so the rewritten image references resolve.
    """
    result = clean_markdown(raw_text)
    output_path.write_text(result.text, encoding="utf-8")

    if result.media_dir_rename is None or media_dir is None:
        return

    _, new_name = result.media_dir_rename
    new_dir = output_path.parent / new_name
    if media_dir.exists() and not new_dir.exists() and media_dir != new_dir:
        media_dir.rename(new_dir)
