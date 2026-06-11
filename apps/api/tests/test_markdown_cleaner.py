"""Unit tests for ``app.processors.markdown_cleaner.clean_markdown``."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.processors import CleanResult, clean_markdown
from app.processors.markdown_cleaner import slugify

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def dirty_sample() -> str:
    return (FIXTURES_DIR / "sample_dirty.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cleaned(dirty_sample: str) -> CleanResult:
    return clean_markdown(dirty_sample)


# ---------------------------------------------------------------------------
# Tag-level invariants
# ---------------------------------------------------------------------------


def test_no_svg_remains(cleaned: CleanResult) -> None:
    assert "<svg" not in cleaned.text
    assert "xlink:href" not in cleaned.text


def test_no_span_wrapper_remains(cleaned: CleanResult) -> None:
    assert "<span" not in cleaned.text
    assert "</span>" not in cleaned.text


def test_no_div_remains(cleaned: CleanResult) -> None:
    assert "<div" not in cleaned.text
    assert "</div>" not in cleaned.text


def test_no_table_scaffold_remains(cleaned: CleanResult) -> None:
    for tag in ("<table", "</table", "<tbody", "<tr>", "<td", "<colgroup", "<col "):
        assert tag not in cleaned.text


def test_no_paragraph_tag_remains(cleaned: CleanResult) -> None:
    assert "<p>" not in cleaned.text
    assert "</p>" not in cleaned.text


def test_no_xhtml_anchor_links(cleaned: CleanResult) -> None:
    assert ".xhtml" not in cleaned.text


# ---------------------------------------------------------------------------
# Content survives
# ---------------------------------------------------------------------------


def test_frontmatter_preserved(cleaned: CleanResult) -> None:
    assert cleaned.text.startswith("---")
    assert "title: CODING PROFESSIONALE con CLAUDE CODE IN 24 ORE (Italian Edition)" in cleaned.text


def test_chapter_heading_intact(cleaned: CleanResult) -> None:
    assert "# ORA 1 — Installazione e primo contatto" in cleaned.text


def test_subheading_unwrapped(cleaned: CleanResult) -> None:
    # ``### <span class="class_sMPW">Sistema operativo</span>`` → ``### Sistema operativo``
    assert "### Sistema operativo" in cleaned.text
    assert "### Conclusione" in cleaned.text


def test_external_anchor_becomes_markdown_link(cleaned: CleanResult) -> None:
    assert "[Anthropic](https://anthropic.com)" in cleaned.text


def test_toc_text_survives_after_xhtml_strip(cleaned: CleanResult) -> None:
    assert "Manifesto Strategico" in cleaned.text
    assert "Prefazione" in cleaned.text
    assert "Perché questo manuale" in cleaned.text


# ---------------------------------------------------------------------------
# Callouts
# ---------------------------------------------------------------------------


def test_green_callout_is_blockquote(cleaned: CleanResult) -> None:
    assert "> **✅  I box verdi**" in cleaned.text
    assert "Contengono suggerimenti pratici" in cleaned.text


def test_orange_callout_is_blockquote(cleaned: CleanResult) -> None:
    assert "> **⚠️  I box arancioni**" in cleaned.text


def test_blue_callout_is_blockquote(cleaned: CleanResult) -> None:
    assert "> **💡  I box blu**" in cleaned.text


# ---------------------------------------------------------------------------
# Images & media folder
# ---------------------------------------------------------------------------


def test_image_paths_flattened(cleaned: CleanResult) -> None:
    assert "media/image_rsrcMRV.jpg" in cleaned.text
    assert "media/image_rsrcMRW.jpg" in cleaned.text
    # Bloated path is gone everywhere.
    assert "_z-lib.sk_media" not in cleaned.text
    assert "8743ebd0834b4e528881c09e0416bc7d" not in cleaned.text


def test_media_dir_rename_reported(cleaned: CleanResult) -> None:
    assert cleaned.media_dir_rename is not None
    old, new = cleaned.media_dir_rename
    assert old.endswith("_media")
    assert new == "media"


# ---------------------------------------------------------------------------
# Quoted block transformation
# ---------------------------------------------------------------------------


def test_quoted_div_becomes_blockquote(cleaned: CleanResult) -> None:
    assert '> "Analizza questo repository e dimmi:' in cleaned.text
    assert "> 1. Che tipo di applicazione è" in cleaned.text
    assert '> 2. Che stack tecnologico usa"' in cleaned.text


# ---------------------------------------------------------------------------
# Whitespace
# ---------------------------------------------------------------------------


def test_no_runs_of_blank_lines(cleaned: CleanResult) -> None:
    assert "\n\n\n" not in cleaned.text


def test_no_trailing_spaces(cleaned: CleanResult) -> None:
    for line in cleaned.text.splitlines():
        assert line == line.rstrip()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def test_stats_record_each_stage(cleaned: CleanResult) -> None:
    s = cleaned.stats
    assert s["svg_removed"] >= 1
    assert s["callouts_converted"] >= 3
    assert s["spans_removed"] >= 1
    assert s["divs_removed"] >= 1
    assert s["xhtml_anchors_dropped"] >= 1
    assert s["external_anchors_converted"] == 1
    assert s["paragraphs_unwrapped"] >= 1
    assert s["image_paths_rewritten"] >= 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_clean_is_idempotent() -> None:
    """Running the cleaner twice produces the same output."""
    raw = (FIXTURES_DIR / "sample_dirty.md").read_text(encoding="utf-8")
    once = clean_markdown(raw).text
    twice = clean_markdown(once).text
    assert once == twice


def test_clean_handles_empty_text() -> None:
    result = clean_markdown("")
    assert result.text == "\n"
    assert result.media_dir_rename is None


def test_clean_plain_markdown_is_noop_apart_from_whitespace() -> None:
    raw = "# Hello\n\nThis is plain markdown with no HTML.\n"
    result = clean_markdown(raw)
    assert result.text.strip() == raw.strip()
    assert result.stats["spans_removed"] == 0
    assert result.stats["divs_removed"] == 0
    assert result.media_dir_rename is None


def test_slugify_handles_unicode() -> None:
    assert slugify("Perché questo manuale") == "perche-questo-manuale"
    assert slugify("ORA 1 — Installazione") == "ora-1-installazione"
    assert slugify("Manifesto Strategico") == "manifesto-strategico"
