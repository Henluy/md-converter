"""Tests for the PDF text-vs-scanned heuristic."""

from __future__ import annotations

from pathlib import Path

from app.utils import PdfFlavour, inspect_pdf


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
