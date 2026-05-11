"""Root-level pytest fixtures.

Tests run without a real Postgres unless DATABASE_URL points to one.
We seed dummy env vars before any app import so config.Settings validates.
"""

from __future__ import annotations

import os
import shutil
import uuid
import zipfile
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Preload native C extensions before any test module is collected.

    Importing pymupdf after numpy/onnxruntime (pulled in transitively by
    markitdown during earlier tests) segfaults on macOS aarch64.
    Forcing pymupdf to load first sidesteps the issue.
    """
    del config
    try:
        import pymupdf  # noqa: F401
        import pymupdf4llm  # noqa: F401
    except ImportError:
        pass


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Skip Python's normal shutdown to dodge a pymupdf finaliser SIGSEGV.

    PyMuPDF's atexit/finalisation crashes on macOS aarch64 (Python 3.11+).
    The crash happens AFTER the test summary is printed and AFTER all
    fixtures tore down, so we can safely short-circuit via ``os._exit`` to
    surface the real test exit status to CI.
    """
    del session
    import os
    import sys

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exitstatus)

# Seed env BEFORE the app modules import settings.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    """Drop the lru_cache so each test session reads the seeded env."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """In-process AsyncClient against the FastAPI ASGI app."""
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --------------------------------------------------------------------------
# Shared converter fixtures — used by tests/converters and tests/tasks.
# --------------------------------------------------------------------------

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


def build_epub(path: Path) -> Path:
    """Create a minimal valid EPUB 3 archive at ``path``."""
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
    """Freshly-built minimal EPUB file."""
    return build_epub(tmp_path / "sample.epub")


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


# --------------------------------------------------------------------------
# PDF / DOCX / HTML / TXT generators — used by ticket-8a converter tests.
# --------------------------------------------------------------------------


def build_text_pdf(path: Path, *, lines: int = 40) -> Path:
    """Build a text-native PDF with enough characters to clear the inspector.

    We write multiple lines so the char/pixel ratio comfortably exceeds the
    default threshold (1e-4) and the heuristic classifies the page as native.
    The first line is "Hello md-converter" so converter assertions still pass.
    """
    import pymupdf

    body_line = "The quick brown fox jumps over the lazy dog. " * 3
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), "Hello md-converter", fontsize=14)
        for i in range(lines):
            page.insert_text((72, 110 + i * 14), body_line, fontsize=11)
        doc.save(str(path))
    return path


def build_scanned_pdf(path: Path) -> Path:
    """Build a PDF that contains only an image — the 'scanned' baseline.

    We rasterise a single image-only page so text extraction returns nothing
    and the inspector falls below the char/pixel threshold.
    """
    import pymupdf

    with pymupdf.open() as doc:
        page = doc.new_page()
        # Solid grey rectangle stands in for a scan; no text glyphs at all.
        page.draw_rect(page.rect, color=(0.8, 0.8, 0.8), fill=(0.8, 0.8, 0.8))
        doc.save(str(path))
    return path


def build_docx(path: Path, *, text: str = "Hello from docx") -> Path:
    """Build a fully-formed .docx using python-docx so markitdown accepts it."""
    import docx  # python-docx, declared in [dependency-groups].dev

    document = docx.Document()
    document.add_paragraph(text)
    document.save(str(path))
    return path


@pytest.fixture
def text_pdf(tmp_path: Path) -> Path:
    return build_text_pdf(tmp_path / "text.pdf")


@pytest.fixture
def scanned_pdf(tmp_path: Path) -> Path:
    return build_scanned_pdf(tmp_path / "scan.pdf")


@pytest.fixture
def docx_file(tmp_path: Path) -> Path:
    return build_docx(tmp_path / "doc.docx")


@pytest.fixture
def html_file(tmp_path: Path) -> Path:
    path = tmp_path / "page.html"
    path.write_text(
        "<!doctype html><html><body><h1>Hello</h1><p>From <em>md-converter</em>.</p></body></html>",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def txt_file(tmp_path: Path) -> Path:
    path = tmp_path / "note.txt"
    path.write_text("Hello from a plain text file.\n", encoding="utf-8")
    return path
