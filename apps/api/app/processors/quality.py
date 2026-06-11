"""Conversion quality / confidence heuristic.

Converters tell us *whether* they succeeded; this tells us *how well*. The
output is a coarse confidence signal (0.0 to 1.0 + a high/medium/low band) plus
human-readable warnings, persisted alongside the file so the UI can flag
conversions that deserve a manual look.

Pure and deterministic — no I/O, no converter coupling — so it's cheap to
unit-test and safe to call from the worker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A source this big yielding almost no text is almost certainly a failed or
# partial extraction (e.g. a scanned PDF that slipped through, a DRM'd EPUB).
_SMALL_INPUT_FLOOR = 20_000  # bytes
_SMALL_OUTPUT_FLOOR = 200  # chars
# Above this we expect *some* structure; a long wall of text with no heading
# usually means heading detection failed.
_STRUCTURE_FLOOR = 2_000  # chars

_RE_HEADING = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_REPLACEMENT_CHAR = "�"

_HIGH = 0.75
_MEDIUM = 0.45


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    """Coarse confidence signal for one converted document."""

    score: float  # 0.0 to 1.0
    level: str  # "high" | "medium" | "low"
    warnings: list[str] = field(default_factory=list)
    signals: dict[str, float | int] = field(default_factory=dict)


def _level_for(score: float) -> str:
    if score >= _HIGH:
        return "high"
    if score >= _MEDIUM:
        return "medium"
    return "low"


def assess_quality(
    *,
    input_bytes: int,
    markdown: str,
    pages: int | None = None,
) -> QualityAssessment:
    """Score a conversion's output. Higher is more trustworthy."""
    text = markdown.strip()
    chars = len(text)
    heading_count = len(_RE_HEADING.findall(markdown))
    replacement_count = markdown.count(_REPLACEMENT_CHAR)

    signals: dict[str, float | int] = {
        "input_bytes": input_bytes,
        "chars": chars,
        "heading_count": heading_count,
        "replacement_count": replacement_count,
        "pages": pages if pages is not None else 0,
    }

    if chars == 0:
        return QualityAssessment(
            score=0.0,
            level="low",
            warnings=["Conversion produced no text content."],
            signals=signals,
        )

    score = 1.0
    warnings: list[str] = []

    if input_bytes >= _SMALL_INPUT_FLOOR and chars < _SMALL_OUTPUT_FLOOR:
        score -= 0.7
        warnings.append(
            f"Output is suspiciously small ({chars} chars) for a "
            f"{input_bytes // 1024} KB source — extraction may be incomplete."
        )

    if chars >= _STRUCTURE_FLOOR and heading_count == 0:
        score -= 0.2
        warnings.append(
            "No headings detected — the document structure may have been lost."
        )

    if replacement_count > 0:
        score -= min(0.4, 0.1 + 0.05 * replacement_count)
        warnings.append(
            f"{replacement_count} replacement character(s) present — "
            "the source may have an encoding problem."
        )

    score = max(0.0, min(1.0, score))
    return QualityAssessment(
        score=round(score, 3),
        level=_level_for(score),
        warnings=warnings,
        signals=signals,
    )
