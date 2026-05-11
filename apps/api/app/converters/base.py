"""Strategy interface for all document → markdown converters.

Every converter sub-class:
- declares which file extensions it supports (lower-case, dot-prefixed),
- implements ``convert(input_path, output_dir)`` returning a ``ConversionResult``.

Routing/format-detection lives in ``router.py`` (ticket 7). Each converter
remains self-contained and unaware of the others, so we can compose or
swap them freely.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

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
