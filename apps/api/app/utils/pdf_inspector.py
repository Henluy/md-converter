"""PDF inspector — decide whether a PDF is text-native or scanned.

Heuristic (BRIEF §5, hardened):

  1. Sample pages spread *evenly across the whole document* (not just the
     first few) so cover art, blank leaves and image-heavy front matter
     don't dominate the verdict.
  2. For each sampled page, compute its own char/pixel ratio
     (``len(get_text)`` / ``width*height`` at 72 dpi, the PDF default unit).
  3. A page counts as "text" when its ratio clears ``page_threshold``.
  4. Classify the document ``text_native`` when at least
     ``min_text_page_ratio`` of the sampled pages are text pages; otherwise
     ``scanned``.

Deciding on the *fraction of text pages* rather than one global ratio makes
the call robust to outliers: a single huge image page can't drag a
text-native book below the line, and a few stray words can't lift a scanned
document above it.

The thresholds are conservative — typical text-native pages sit around 0.001
chars/pixel (~600 chars on a US letter page at 72 dpi). Scanned pages
usually return < 0.0001 because extraction yields almost nothing for
image-only pages.

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
    #: Global chars/pixel over the sampled pages (kept as a reported signal).
    char_pixel_ratio: float | None = None
    #: Fraction of sampled pages that carried extractable text (0.0 to 1.0).
    text_page_ratio: float | None = None


DEFAULT_THRESHOLD = 1e-4  # chars per pixel — a page clears this to count as text
DEFAULT_SAMPLE_PAGES = 8
DEFAULT_MIN_TEXT_PAGE_RATIO = 0.4  # ≥40% text pages → text-native


def _sample_indices(page_count: int, k: int) -> list[int]:
    """Pick ``k`` page indices spread evenly across ``[0, page_count - 1]``.

    Deduplicated and sorted; returns fewer than ``k`` when the document has
    fewer pages than requested.
    """
    k = min(k, page_count)
    if k <= 0:
        return []
    if k == 1:
        return [0]
    step = (page_count - 1) / (k - 1)
    return sorted({round(i * step) for i in range(k)})


def inspect_pdf(
    pdf_path: Path,
    *,
    sample_pages: int = DEFAULT_SAMPLE_PAGES,
    threshold: float = DEFAULT_THRESHOLD,
    min_text_page_ratio: float = DEFAULT_MIN_TEXT_PAGE_RATIO,
) -> PdfInspection:
    """Classify a PDF as text-native or scanned by sampling pages across it."""
    try:
        import pymupdf
    except ImportError:
        return PdfInspection(flavour=PdfFlavour.unknown)

    sampled = 0
    try:
        with pymupdf.open(str(pdf_path)) as doc:
            if doc.page_count == 0:
                return PdfInspection(flavour=PdfFlavour.unknown)

            indices = _sample_indices(doc.page_count, sample_pages)
            sampled = len(indices)
            total_chars = 0
            total_pixels = 0.0
            text_pages = 0
            for i in indices:
                page = doc.load_page(i)
                chars = len((page.get_text("text") or "").strip())
                rect = page.rect
                pixels = float(rect.width) * float(rect.height)
                total_chars += chars
                total_pixels += pixels
                if pixels > 0 and (chars / pixels) >= threshold:
                    text_pages += 1
    except pymupdf.FileDataError:
        return PdfInspection(flavour=PdfFlavour.unknown)

    if total_pixels <= 0 or sampled == 0:
        return PdfInspection(flavour=PdfFlavour.unknown, sampled_pages=sampled)

    char_pixel_ratio = total_chars / total_pixels
    text_page_ratio = text_pages / sampled
    flavour = (
        PdfFlavour.text_native
        if text_page_ratio >= min_text_page_ratio
        else PdfFlavour.scanned
    )
    return PdfInspection(
        flavour=flavour,
        sampled_pages=sampled,
        char_pixel_ratio=char_pixel_ratio,
        text_page_ratio=text_page_ratio,
    )
