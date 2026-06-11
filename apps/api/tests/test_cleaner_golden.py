"""Golden-master regression test for the markdown cleaner.

Pins the cleaner's output on a real-world dirty EPUB sample so that any
future change (e.g. swapping regex stripping for an HTML parser) cannot
silently alter the result. The diff *is* the review.

Regenerate intentionally after an approved change:

    UPDATE_GOLDEN=1 uv run pytest tests/test_cleaner_golden.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.processors import clean_markdown

_FIXTURES = Path(__file__).parent / "fixtures"
_DIRTY = _FIXTURES / "sample_dirty.md"
_GOLDEN = _FIXTURES / "sample_dirty.golden.md"


def test_cleaner_output_matches_golden() -> None:
    dirty = _DIRTY.read_text(encoding="utf-8")
    result = clean_markdown(dirty)

    if os.environ.get("UPDATE_GOLDEN"):
        _GOLDEN.write_text(result.text, encoding="utf-8")
        pytest.skip("golden file regenerated (UPDATE_GOLDEN=1)")

    assert _GOLDEN.exists(), "missing golden; run once with UPDATE_GOLDEN=1"
    assert result.text == _GOLDEN.read_text(encoding="utf-8")


def test_cleaned_sample_has_no_raw_html_residue() -> None:
    """Invariants that must hold regardless of the exact golden bytes."""
    result = clean_markdown(_DIRTY.read_text(encoding="utf-8"))
    text = result.text
    for tag in ("<span", "<div", "<svg", "<table", "<td", "<p>", "<img"):
        assert tag not in text, f"{tag!r} leaked into cleaned output"
    # The flat media path rewrite must have collapsed the absurd UUID path.
    assert "_media/" not in text
    assert "media/image_rsrcMRV.jpg" in text
