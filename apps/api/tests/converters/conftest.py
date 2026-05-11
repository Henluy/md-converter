"""Fixtures for converter tests.

We build a minimal but valid EPUB 3 archive on the fly so tests stay
hermetic — no binary fixture committed, no network access.
"""

from __future__ import annotations

import shutil
import textwrap
import uuid
import zipfile
from pathlib import Path

import pytest

_CONTAINER_XML = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

_CONTENT_OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:{uid}</dc:identifier>
    <dc:title>md-converter Test Book</dc:title>
    <dc:language>en</dc:language>
    <meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="ch1"/>
  </spine>
</package>
"""

_NAV_XHTML = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <head><title>Nav</title></head>
  <body>
    <nav epub:type="toc"><ol><li><a href="chapter1.xhtml">Chapter One</a></li></ol></nav>
  </body>
</html>
"""

_CHAPTER_XHTML = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Chapter One</title></head>
  <body>
    <h1>Chapter One</h1>
    <p>This is a short paragraph with <em>italics</em> and <strong>bold</strong>.</p>
    <ul>
      <li>First bullet</li>
      <li>Second bullet</li>
    </ul>
  </body>
</html>
"""


def _build_epub(path: Path) -> Path:
    """Create a minimal valid EPUB 3 file at ``path``."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # The 'mimetype' file MUST be first, uncompressed (EPUB spec).
        zf.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr("META-INF/container.xml", _CONTAINER_XML)
        zf.writestr(
            "OEBPS/content.opf",
            _CONTENT_OPF.format(uid=uuid.uuid4()),
        )
        zf.writestr("OEBPS/nav.xhtml", _NAV_XHTML)
        zf.writestr("OEBPS/chapter1.xhtml", _CHAPTER_XHTML)
    return path


@pytest.fixture
def epub_file(tmp_path: Path) -> Path:
    """Path to a freshly-built minimal EPUB."""
    return _build_epub(tmp_path / "sample.epub")


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    return tmp_path / "out"


@pytest.fixture
def pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


@pytest.fixture
def skip_if_no_pandoc(pandoc_available: bool) -> None:
    if not pandoc_available:
        pytest.skip("pandoc binary not available on this host")


# Used in the fake-binary test.
@pytest.fixture
def fake_failing_pandoc(tmp_path: Path) -> Path:
    """A tiny shell script that mimics a failing pandoc invocation."""
    script = tmp_path / "fake_pandoc"
    script.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            echo "boom" >&2
            exit 5
            """
        )
    )
    script.chmod(0o755)
    return script
