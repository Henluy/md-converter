"""PDF inspector — decide whether a PDF is text-native or scanned.

Heuristic (BRIEF §5):

  1. Sample the first ``sample_pages`` pages.
  2. Sum extractable characters (``page.get_text("text")``).
  3. Sum the rendering area in pixels (``rect.width * rect.height``, at 72 dpi
     which is the PDF default unit so this is a stable proxy).
  4. If the char/pixel ratio falls below ``threshold``, the document is
     classified as scanned; otherwise it's text-native.

The threshold is conservative — typical text-native pages sit around 0.001
chars/pixel (~600 chars on a US letter page at 72 dpi). Scanned pages
usually return < 0.0001 because pdfminer-style extraction yields almost
nothing for image-only pages.

pymupdf is imported lazily to avoid clashes with pytest's assertion
rewriter at module import time.
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


DEFAULT_THRESHOLD = 1e-4  # chars per pixel


def inspect_pdf(
    pdf_path: Path,
    *,
    sample_pages: int = 3,
    threshold: float = DEFAULT_THRESHOLD,
) -> PdfInspection:
    """Classify a PDF as text-native or scanned by sampling its first pages."""
    try:
        import pymupdf
    except ImportError:
        return PdfInspection(flavour=PdfFlavour.unknown)

    n = 0
    try:
        with pymupdf.open(str(pdf_path)) as doc:
            if doc.page_count == 0:
                return PdfInspection(flavour=PdfFlavour.unknown)

            n = min(sample_pages, doc.page_count)
            total_chars = 0
            total_pixels = 0.0
            for i in range(n):
                page = doc.load_page(i)
                text = page.get_text("text") or ""
                total_chars += len(text.strip())
                rect = page.rect
                total_pixels += float(rect.width) * float(rect.height)
    except pymupdf.FileDataError:
        return PdfInspection(flavour=PdfFlavour.unknown)

    if total_pixels <= 0:
        return PdfInspection(flavour=PdfFlavour.unknown, sampled_pages=n)

    ratio = total_chars / total_pixels
    flavour = PdfFlavour.text_native if ratio >= threshold else PdfFlavour.scanned
    return PdfInspection(
        flavour=flavour,
        sampled_pages=n,
        char_pixel_ratio=ratio,
    )
