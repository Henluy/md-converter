"""PDF inspector — decide whether a PDF is text-native or scanned.

Ticket 7 ships an interface and a conservative default (assume text-native);
ticket 8 plugs in pymupdf-based heuristics described in BRIEF §5 (sample 3
pages, ratio of extractable characters to pixels).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class PdfFlavour(StrEnum):
    text_native = "text_native"
    scanned = "scanned"
    unknown = "unknown"


@dataclass(frozen=True, slots=True)
class PdfInspection:
    """Outcome of a PDF inspection pass."""

    flavour: PdfFlavour
    sampled_pages: int = 0
    char_pixel_ratio: float | None = None


def inspect_pdf(_pdf_path: Path, *, sample_pages: int = 3) -> PdfInspection:
    """Return whether the PDF is text-native or scanned.

    Stub implementation (ticket 7): always returns ``text_native``.
    Ticket 8 will sample pages with pymupdf and compute a real ratio.
    """
    del sample_pages  # placeholder; real heuristic lands at ticket 8
    return PdfInspection(flavour=PdfFlavour.text_native)
