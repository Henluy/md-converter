"""Tests for the conversion quality / confidence heuristic."""

from __future__ import annotations

from app.processors import assess_quality


def test_structured_output_is_high_confidence() -> None:
    md = (
        "# Title\n\nA real paragraph of prose with several sentences.\n\n"
        "## Section\n\nMore meaningful content goes here, plenty of it.\n"
    )
    a = assess_quality(input_bytes=10_000, markdown=md, pages=5)
    assert a.level == "high"
    assert a.score >= 0.75
    assert a.warnings == []


def test_empty_output_is_low_confidence() -> None:
    a = assess_quality(input_bytes=10_000, markdown="", pages=1)
    assert a.level == "low"
    assert a.score == 0.0
    assert a.warnings  # non-empty


def test_tiny_output_for_large_input_warns_and_is_low() -> None:
    a = assess_quality(input_bytes=500_000, markdown="a few words only", pages=120)
    assert a.level == "low"
    assert any("small" in w.lower() for w in a.warnings)


def test_long_flat_text_without_headings_warns() -> None:
    md = "Just some flat text without any structure. " * 200  # > 2000 chars
    a = assess_quality(input_bytes=30_000, markdown=md, pages=10)
    assert any(
        "heading" in w.lower() or "structure" in w.lower() for w in a.warnings
    )


def test_replacement_characters_flag_encoding_issue() -> None:
    md = "# Title\n\n" + "caf� and m�jibake everywhere here. " * 30
    a = assess_quality(input_bytes=5_000, markdown=md, pages=2)
    assert any(
        "encoding" in w.lower() or "replacement" in w.lower() for w in a.warnings
    )


def test_score_is_clamped_between_zero_and_one() -> None:
    a = assess_quality(input_bytes=1_000_000, markdown="�" * 50, pages=300)
    assert 0.0 <= a.score <= 1.0


def test_signals_are_reported() -> None:
    a = assess_quality(input_bytes=10_000, markdown="# A\n\ntext", pages=3)
    assert a.signals["heading_count"] == 1
    assert a.signals["chars"] > 0
    assert a.signals["pages"] == 3
