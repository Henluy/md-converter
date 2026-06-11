"""The cleaner is robust to HTML residue from *any* publisher, not just the
one whose class names the targeted regexes were tuned on."""

from __future__ import annotations

from app.processors import clean_markdown


def test_strips_unknown_block_and_inline_html() -> None:
    dirty = (
        '<section class="weird_pub_X">\n\n'
        '<figure><img src="a_media/x.png" alt="cover" />'
        "<figcaption>Caption</figcaption></figure>\n\n"
        "<aside>Side note</aside>\n\n"
        "Body with <strong>bold</strong>, <em>italic</em> and a line<br/>break.\n\n"
        "<hr/>\n\n"
        "A <cite>citation</cite> and <sup>note</sup>.\n\n"
        "</section>\n"
    )
    text = clean_markdown(dirty).text

    for tag in (
        "<section",
        "<figure",
        "<figcaption",
        "<aside",
        "<strong",
        "<em",
        "<br",
        "<hr",
        "<cite",
        "<sup",
    ):
        assert tag not in text, f"{tag!r} leaked into cleaned output"

    # Inner content is preserved…
    assert "Caption" in text
    assert "Side note" in text
    assert "citation" in text
    # …emphasis is promoted to markdown, not dropped…
    assert "**bold**" in text
    assert "*italic*" in text
    # …<hr> becomes a thematic break, <img> + media rewrite still works.
    assert "---" in text
    assert "media/x.png" in text
