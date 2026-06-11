"""Clean raw markdown produced by EPUB/PDF/DOCX converters.

The converters (especially Pandoc on EPUB) emit a lot of HTML residue:
``<span class="class_sMPS">…</span>`` wrappers around every sentence,
empty ``<div>`` spacers, fake-table "callouts" that should really be
blockquotes, broken ``#cXX.xhtml`` anchors, and absurd image paths that
embed the job UUID + content hash. This module turns that mess into
GitHub-flavoured markdown that renders correctly anywhere.

Public surface: ``clean_markdown(text) -> CleanResult``.

The pipeline is intentionally pure (no I/O, no filesystem). Image-path
rewriting happens in the markdown text; the *caller* (the converter)
moves the actual media folder on disk if it wants the new paths to
resolve. See ``CleanResult.media_dir_rename`` for the suggested rename.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

# The flat directory name we collapse every per-job media folder into.
# Pandoc creates e.g. ``<job_uuid>/<file_hex>_<stem>_media/``; after cleanup
# all image references point to ``media/<basename>`` and the caller is
# expected to rename the on-disk folder to match.
DEFAULT_MEDIA_DIR_NAME = "media"


@dataclass(frozen=True, slots=True)
class CleanResult:
    """Outcome of a cleanup pass."""

    text: str
    #: ``(old_media_folder_name, new_media_folder_name)`` if image paths
    #: were rewritten, otherwise ``None``. The caller renames the folder
    #: on disk; this module only rewrites the references in markdown.
    media_dir_rename: tuple[str, str] | None = None
    #: Per-stage counters, for warnings & telemetry.
    stats: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Regex catalogue
# ---------------------------------------------------------------------------

# Whole ``<svg>…</svg>`` block (EPUB covers wrap a jpg in an svg shell).
_RE_SVG_BLOCK = re.compile(r"<svg\b[^>]*>.*?</svg>", flags=re.DOTALL | re.IGNORECASE)

# Single-cell HTML table — Pandoc renders EPUB call-out boxes this way.
_RE_SINGLE_CELL_TABLE = re.compile(
    r"<table\b[^>]*>\s*"
    r"(?:<colgroup\b[^>]*>.*?</colgroup>\s*)?"
    r"<tbody>\s*<tr>\s*<td\b[^>]*>(?P<body>.*?)</td>\s*</tr>\s*</tbody>\s*"
    r"</table>",
    flags=re.DOTALL | re.IGNORECASE,
)

# Inner <p>…</p> tags (used when unpacking a call-out's body).
_RE_INNER_P = re.compile(
    r"<p\b[^>]*>(.*?)</p>",
    flags=re.DOTALL | re.IGNORECASE,
)

# Generic table scaffold tags left over after callout conversion.
_RE_TABLE_SCAFFOLD = re.compile(
    r"</?(?:table|tbody|thead|tfoot|tr|colgroup|col|caption)\b[^>]*/?>",
    flags=re.IGNORECASE,
)
_RE_TD_OPEN = re.compile(r"<t[dh]\b[^>]*>", flags=re.IGNORECASE)
_RE_TD_CLOSE = re.compile(r"</t[dh]>", flags=re.IGNORECASE)

# Anchors pointing back into the EPUB's xhtml chapter files. These
# never resolve in markdown — drop the href, keep the visible text.
_RE_XHTML_ANCHOR = re.compile(
    r"<a\s+[^>]*href=\"#[^\"]*\.xhtml[^\"]*\"[^>]*>(?P<text>.*?)</a>",
    flags=re.DOTALL | re.IGNORECASE,
)
_RE_EXTERNAL_ANCHOR = re.compile(
    r"<a\s+[^>]*href=\"(?P<href>https?://[^\"]+)\"[^>]*>(?P<text>.*?)</a>",
    flags=re.DOTALL | re.IGNORECASE,
)
_RE_FALLBACK_ANCHOR = re.compile(
    r"<a\b[^>]*>(?P<text>.*?)</a>",
    flags=re.DOTALL | re.IGNORECASE,
)

# Markdown links that point back into the EPUB's xhtml chapters —
# ``[Perché questo manuale](#cEP.xhtml_aKKJ)`` — also unresolvable.
_RE_XHTML_MD_LINK = re.compile(
    r"\[(?P<text>[^\]]*)\]\(#[^)]*\.xhtml[^)]*\)",
)

# Empty ``<span id="…"></span>`` anchor markers Pandoc sprinkles in.
_RE_EMPTY_SPAN = re.compile(
    r"<span\b[^>]*></span>",
    flags=re.IGNORECASE,
)

# General span — strip the wrapper, keep the inner text. Non-greedy.
_RE_SPAN_WRAPPER = re.compile(
    r"<span\b[^>]*>(.*?)</span>",
    flags=re.DOTALL | re.IGNORECASE,
)

# Standalone opening/closing div tags. Divs are block-level so we strip
# them individually rather than matched-pair.
_RE_DIV_OPEN = re.compile(r"<div\b[^>]*>", flags=re.IGNORECASE)
_RE_DIV_CLOSE = re.compile(r"</div>", flags=re.IGNORECASE)

# Orphan span open/close tags — the source occasionally drops the closing
# tag (e.g. ``### <span class="class_sMPW">Le sezioni chiave`` with no
# ``</span>``), which makes ``_RE_SPAN_WRAPPER`` skip the line. Run a
# final standalone-tag pass to mop those up.
_RE_SPAN_OPEN_ORPHAN = re.compile(r"<span\b[^>]*>", flags=re.IGNORECASE)
_RE_SPAN_CLOSE_ORPHAN = re.compile(r"</span>", flags=re.IGNORECASE)

# <p>…</p> as block-level paragraph (after we've moved past callouts).
_RE_P_BLOCK = re.compile(
    r"<p\b[^>]*>(?P<body>.*?)</p>",
    flags=re.DOTALL | re.IGNORECASE,
)

# <img …> → markdown image (or empty, if no src).
_RE_IMG_TAG = re.compile(
    r"<img\b(?P<attrs>[^>]*)/?>",
    flags=re.IGNORECASE,
)
_RE_IMG_SRC = re.compile(r"src=\"(?P<src>[^\"]+)\"", flags=re.IGNORECASE)
_RE_IMG_ALT = re.compile(r"alt=\"(?P<alt>[^\"]*)\"", flags=re.IGNORECASE)

# Image-path rewrite. We match any path segment ending in ``_media``
# followed by the actual file. The leading path (UUIDs, hashes,
# absolute components) is discarded.
_RE_MEDIA_PATH = re.compile(
    r"(?P<prefix>[^\s\"'()\[\]]*?)(?P<dir>[^\s/\"'()\[\]]+_media)/(?P<file>[^\s\"'()\[\]]+\.(?:jpg|jpeg|png|gif|svg|webp|bmp))",
    flags=re.IGNORECASE,
)

# Callout emoji set — covers the four "box" colours used in the source
# EPUB plus a handful of common ones seen in technical books.
_CALLOUT_EMOJIS = {"✅", "⚠️", "💡", "🎯", "📝", "📌", "🚨", "🔥", "ℹ️", "❗"}  # noqa: RUF001

# Quoted-passage div Pandoc uses for code-style indented snippets.
# We promote it to a blockquote so it visually stands out.
_RE_QUOTED_DIV = re.compile(
    r"<div\b[^>]*class=\"class_sM3\"[^>]*>(?P<body>.*?)</div>",
    flags=re.DOTALL | re.IGNORECASE,
)

# --- Residual HTML safety net (publisher-agnostic) ----------------------
# The targeted passes above clean the EPUB toolchain we tuned on. Other
# publishers emit different structural/inline tags; rather than leak them as
# raw HTML, we map the meaningful ones to markdown and strip the rest,
# keeping inner text. Tag-name-driven (not class-driven), so it generalises.
_RE_BR = re.compile(r"<br\b[^>]*/?>", flags=re.IGNORECASE)
_RE_HR = re.compile(r"<hr\b[^>]*/?>", flags=re.IGNORECASE)
# Open *and* close both map to the same marker, so <strong>x</strong> → **x**.
_RE_STRONG_TAG = re.compile(r"</?(?:strong|b)\b[^>]*>", flags=re.IGNORECASE)
_RE_EM_TAG = re.compile(r"</?(?:em|i)\b[^>]*>", flags=re.IGNORECASE)
_RE_CODE_TAG = re.compile(r"</?code\b[^>]*>", flags=re.IGNORECASE)
# Structural / inline wrappers that are safe to drop (keep their text).
_RE_RESIDUAL_TAG = re.compile(
    r"</?(?:section|article|aside|figure|figcaption|header|footer|nav|main|"
    r"cite|small|sup|sub|mark|u|abbr|q|s|strike|del|ins|wbr|time|var|kbd|"
    r"samp|address|bdi|bdo|data|dfn|ruby|rt|rp)\b[^>]*/?>",
    flags=re.IGNORECASE,
)

# Whitespace cleanup.
_RE_TRAILING_WS = re.compile(r"[ \t]+$", flags=re.MULTILINE)
_RE_BLANK_RUN = re.compile(r"\n{3,}")

# Heading-row detector for the xhtml-anchor → markdown-anchor mapping
# (currently unused — we drop hrefs entirely — but kept for future use).
_RE_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", flags=re.MULTILINE)

_SLUG_NON_ALPHANUM = re.compile(r"[^\w\s-]", flags=re.UNICODE)
_SLUG_WHITESPACE = re.compile(r"[\s_]+")


def slugify(text: str) -> str:
    """GitHub-style heading slug. Public for future TOC reconstruction."""
    normalised = unicodedata.normalize("NFKD", text)
    ascii_text = normalised.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower().strip()
    stripped = _SLUG_NON_ALPHANUM.sub("", lowered)
    return _SLUG_WHITESPACE.sub("-", stripped).strip("-")


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def _strip_svg(text: str, stats: dict[str, int]) -> str:
    """Remove every ``<svg>…</svg>`` block (EPUB cover wrappers)."""
    text, n = _RE_SVG_BLOCK.subn("", text)
    stats["svg_removed"] = n
    return text


def _convert_callouts(text: str, stats: dict[str, int]) -> str:
    """Single-cell tables that start with a known emoji → blockquote."""
    converted = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal converted
        body = match.group("body").strip()
        paragraphs = [p.strip() for p in _RE_INNER_P.findall(body) if p.strip()]
        if not paragraphs:
            # Not a recognisable callout — leave it for the scaffold strip.
            return match.group(0)
        first = paragraphs[0]
        leading = first.lstrip()[:4]
        if not any(leading.startswith(emoji) for emoji in _CALLOUT_EMOJIS):
            # Not a callout — drop the table wrappers but keep the paragraphs.
            return "\n\n".join(paragraphs) + "\n"
        converted += 1
        head, *rest = paragraphs
        lines = [f"> **{head}**"]
        for para in rest:
            lines.append(">")
            lines.append(f"> {para}")
        return "\n".join(lines) + "\n"

    text = _RE_SINGLE_CELL_TABLE.sub(_replace, text)
    stats["callouts_converted"] = converted
    return text


def _strip_table_scaffold(text: str, stats: dict[str, int]) -> str:
    """Drop any leftover table/tr/td scaffold so the inner prose surfaces."""
    text, scaffold = _RE_TABLE_SCAFFOLD.subn("", text)
    text = _RE_TD_OPEN.sub("", text)
    text = _RE_TD_CLOSE.sub("\n", text)
    stats["table_scaffold_removed"] = scaffold
    return text


def _convert_quoted_div(text: str, stats: dict[str, int]) -> str:
    """``<div class="class_sM3">`` → blockquote of its inner spans."""
    converted = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal converted
        body = match.group("body")
        spans = [s.strip() for s in _RE_SPAN_WRAPPER.findall(body) if s.strip()]
        if not spans:
            return ""
        converted += 1
        return "\n".join(f"> {line}" for line in spans) + "\n"

    text = _RE_QUOTED_DIV.sub(_replace, text)
    stats["quoted_blocks_converted"] = converted
    return text


def _rewrite_anchors(text: str, stats: dict[str, int]) -> str:
    """Drop xhtml ToC anchors (HTML *and* markdown), convert external links."""
    text, xhtml_html = _RE_XHTML_ANCHOR.subn(lambda m: m.group("text"), text)
    text, external = _RE_EXTERNAL_ANCHOR.subn(
        lambda m: f"[{m.group('text')}]({m.group('href')})", text
    )
    text, fallback = _RE_FALLBACK_ANCHOR.subn(lambda m: m.group("text"), text)
    text, xhtml_md = _RE_XHTML_MD_LINK.subn(lambda m: m.group("text"), text)
    stats["xhtml_anchors_dropped"] = xhtml_html + xhtml_md
    stats["external_anchors_converted"] = external
    stats["other_anchors_stripped"] = fallback
    return text


def _strip_spans(text: str, stats: dict[str, int]) -> str:
    """Empty ``<span id>``s first, then wrappers — repeated until stable.

    Finally, sweep any orphan ``<span …>`` opening tags whose closing
    ``</span>`` is missing in the source (Pandoc sometimes drops it on
    multi-line headings), and any stranded ``</span>`` for the same reason.
    """
    text, empties = _RE_EMPTY_SPAN.subn("", text)
    removed = 0
    # Apply repeatedly to cope with nested spans (rare but real).
    while True:
        text, n = _RE_SPAN_WRAPPER.subn(lambda m: m.group(1), text)
        removed += n
        if n == 0:
            break
    text, orphan_open = _RE_SPAN_OPEN_ORPHAN.subn("", text)
    text, orphan_close = _RE_SPAN_CLOSE_ORPHAN.subn("", text)
    stats["empty_spans_removed"] = empties
    stats["spans_removed"] = removed
    stats["orphan_span_tags_removed"] = orphan_open + orphan_close
    return text


def _strip_divs(text: str, stats: dict[str, int]) -> str:
    """Strip every standalone ``<div…>`` / ``</div>`` tag, keep contents."""
    text, opens = _RE_DIV_OPEN.subn("", text)
    text, closes = _RE_DIV_CLOSE.subn("", text)
    stats["divs_removed"] = opens + closes
    return text


def _unwrap_paragraphs(text: str, stats: dict[str, int]) -> str:
    """``<p>x</p>`` → ``x`` with a paragraph break."""
    converted = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal converted
        converted += 1
        inner = match.group("body").strip()
        return f"{inner}\n\n" if inner else ""

    text = _RE_P_BLOCK.sub(_replace, text)
    stats["paragraphs_unwrapped"] = converted
    return text


def _convert_img_tags(text: str, stats: dict[str, int]) -> str:
    """``<img src="x" alt="y">`` → ``![y](x)`` (or empty if no src)."""
    converted = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal converted
        attrs = match.group("attrs")
        src_match = _RE_IMG_SRC.search(attrs)
        if not src_match:
            return ""
        src = src_match.group("src")
        alt_match = _RE_IMG_ALT.search(attrs)
        alt = alt_match.group("alt") if alt_match else ""
        converted += 1
        return f"![{alt}]({src})"

    text = _RE_IMG_TAG.sub(_replace, text)
    stats["img_tags_converted"] = converted
    return text


def _strip_residual_html(text: str, stats: dict[str, int]) -> str:
    """Mop up HTML tags the targeted passes didn't recognise.

    Keeps content fidelity: ``<br>`` → newline, ``<hr>`` → thematic break,
    emphasis tags → markdown emphasis, everything else stripped to its text.
    """
    text = _RE_BR.sub("\n", text)
    text = _RE_HR.sub("\n\n---\n\n", text)
    text = _RE_STRONG_TAG.sub("**", text)
    text = _RE_EM_TAG.sub("*", text)
    text = _RE_CODE_TAG.sub("`", text)
    text, n = _RE_RESIDUAL_TAG.subn("", text)
    stats["residual_html_tags_removed"] = n
    return text


def _rewrite_image_paths(
    text: str,
    stats: dict[str, int],
    media_dir_name: str,
) -> tuple[str, str | None]:
    """Collapse ``…/<x>_media/<file>`` references to ``<media_dir_name>/<file>``.

    Returns the rewritten text and the most-frequently-seen original
    media-folder name (so the caller knows which on-disk folder to rename).
    """
    rewrites = 0
    seen_dirs: dict[str, int] = {}

    def _replace(match: re.Match[str]) -> str:
        nonlocal rewrites
        rewrites += 1
        seen_dirs[match.group("dir")] = seen_dirs.get(match.group("dir"), 0) + 1
        return f"{media_dir_name}/{match.group('file')}"

    text = _RE_MEDIA_PATH.sub(_replace, text)
    stats["image_paths_rewritten"] = rewrites
    if not seen_dirs:
        return text, None
    most_common = max(seen_dirs.items(), key=lambda kv: kv[1])[0]
    return text, most_common


def _normalise_whitespace(text: str) -> str:
    """Strip trailing spaces per line and collapse 3+ blank lines to 2."""
    text = _RE_TRAILING_WS.sub("", text)
    text = _RE_BLANK_RUN.sub("\n\n", text)
    return text.strip() + "\n"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def clean_markdown(
    text: str,
    *,
    media_dir_name: str = DEFAULT_MEDIA_DIR_NAME,
) -> CleanResult:
    """Run the full cleanup pipeline against ``text``.

    The order matters: callouts must be turned into blockquotes *before*
    the generic table scaffold gets stripped, otherwise we lose the
    emoji/title context. Spans are stripped *after* the quoted-div pass
    so the per-line span content is still visible to the blockquote
    converter.
    """
    stats: dict[str, int] = {}

    text = _strip_svg(text, stats)
    text = _convert_callouts(text, stats)
    text = _strip_table_scaffold(text, stats)
    text = _convert_quoted_div(text, stats)
    text = _rewrite_anchors(text, stats)
    text = _strip_spans(text, stats)
    text = _unwrap_paragraphs(text, stats)
    text = _strip_divs(text, stats)
    text = _convert_img_tags(text, stats)
    text = _strip_residual_html(text, stats)
    text, old_media_dir = _rewrite_image_paths(text, stats, media_dir_name)
    text = _normalise_whitespace(text)

    media_dir_rename: tuple[str, str] | None = None
    if old_media_dir is not None and old_media_dir != media_dir_name:
        media_dir_rename = (old_media_dir, media_dir_name)

    return CleanResult(text=text, media_dir_rename=media_dir_rename, stats=stats)
