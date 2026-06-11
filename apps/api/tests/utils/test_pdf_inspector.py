"""Tests for the PDF text-vs-scanned heuristic."""

from __future__ import annotations

from pathlib import Path

from app.utils import PdfFlavour, inspect_pdf


def _build_front_matter_pdf(
    path: Path, *, empty_front: int = 3, text_body: int = 7
) -> Path:
    """A PDF whose first pages are image-only front matter (cover, blanks)
    followed by a text-native body. The classic case the old first-N-pages
    sampling got wrong."""
    import pymupdf

    body_line = "The quick brown fox jumps over the lazy dog. " * 3
    with pymupdf.open() as doc:
        for _ in range(empty_front):
            page = doc.new_page()
            page.draw_rect(page.rect, color=(0.8, 0.8, 0.8), fill=(0.8, 0.8, 0.8))
        for _ in range(text_body):
            page = doc.new_page()
            for i in range(40):
                page.insert_text((72, 80 + i * 14), body_line, fontsize=11)
        doc.save(str(path))
    return path


def test_text_pdf_classified_native(text_pdf: Path) -> None:
    inspection = inspect_pdf(text_pdf)
    assert inspection.flavour == PdfFlavour.text_native
    assert inspection.sampled_pages >= 1
    assert inspection.char_pixel_ratio is not None
    assert inspection.char_pixel_ratio > 0


def test_image_only_pdf_classified_scanned(scanned_pdf: Path) -> None:
    inspection = inspect_pdf(scanned_pdf)
    assert inspection.flavour == PdfFlavour.scanned


def test_corrupt_pdf_returns_unknown(tmp_path: Path) -> None:
    fake = tmp_path / "broken.pdf"
    fake.write_bytes(b"not a pdf at all")
    inspection = inspect_pdf(fake)
    assert inspection.flavour == PdfFlavour.unknown


def test_text_body_after_empty_front_matter_is_native(tmp_path: Path) -> None:
    """Front matter (cover/blank pages) must not flip a text book to scanned.

    Distributed sampling reads pages spread across the document, so the text
    body is seen even when the first pages are image-only.
    """
    pdf = _build_front_matter_pdf(tmp_path / "book.pdf")
    inspection = inspect_pdf(pdf)
    assert inspection.flavour == PdfFlavour.text_native


def test_text_page_ratio_reported_for_text_pdf(text_pdf: Path) -> None:
    inspection = inspect_pdf(text_pdf)
    assert inspection.text_page_ratio == 1.0


def test_text_page_ratio_zero_for_scanned(scanned_pdf: Path) -> None:
    inspection = inspect_pdf(scanned_pdf)
    assert inspection.text_page_ratio == 0.0


def test_mostly_scanned_with_few_text_pages_is_scanned(tmp_path: Path) -> None:
    """A document that is overwhelmingly image-only stays classified scanned
    even if a couple of pages happen to carry a little text."""
    pdf = _build_front_matter_pdf(tmp_path / "scan.pdf", empty_front=9, text_body=1)
    inspection = inspect_pdf(pdf)
    assert inspection.flavour == PdfFlavour.scanned
