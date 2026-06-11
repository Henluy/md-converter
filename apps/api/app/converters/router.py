"""Format-aware converter router (BRIEF §5).

Resolution flow:

  1. Validate extension and MIME (``app.security.detect_format``).
  2. For PDFs, ask ``pdf_inspector`` whether it's text-native or scanned.
  3. Look up the default converter for the resolved format in the registry.
  4. If the caller passed an override, honour it as long as it supports
     the input.

Adding a converter (ticket 8) means registering it; the routing table
itself stays here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.converters.base import BaseConverter
from app.converters.errors import FormatNotSupportedError
from app.security import DetectedFormat, detect_format
from app.utils import PdfFlavour, inspect_pdf


class TargetFormat(StrEnum):
    epub = "epub"
    pdf_native = "pdf_native"
    pdf_scanned = "pdf_scanned"
    docx = "docx"
    html = "html"
    txt = "txt"


# Default converter name per BRIEF §5. Names match the keys in the registry
# passed to ``ConverterRouter``; tickets 8 register the missing pieces.
DEFAULT_BY_FORMAT: dict[TargetFormat, str] = {
    TargetFormat.epub: "pandoc",
    TargetFormat.pdf_native: "pymupdf",
    TargetFormat.pdf_scanned: "ocr",
    TargetFormat.docx: "markitdown",
    TargetFormat.html: "markitdown",
    TargetFormat.txt: "markitdown",
}


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """What the router decided for a given input."""

    target_format: TargetFormat
    detected: DetectedFormat
    converter_name: str
    converter: BaseConverter


class ConverterRouter:
    """Selects the converter that should handle a given file.

    Construct with a mapping of name → instantiated ``BaseConverter``.
    Tests inject a small registry; production wires every converter.
    """

    def __init__(self, registry: dict[str, BaseConverter]) -> None:
        self._registry = registry

    # ---- public API ---------------------------------------------------
    def resolve(
        self,
        input_path: Path,
        *,
        override: str | None = None,
    ) -> RoutingDecision:
        detected = detect_format(input_path)
        target = self._classify(input_path, detected)
        default_name = DEFAULT_BY_FORMAT[target]
        chosen = override or default_name

        converter = self._registry.get(chosen)
        if converter is None:
            raise FormatNotSupportedError(
                f"converter {chosen!r} is not registered (target_format={target})"
            )

        if not converter.supports(input_path):
            raise FormatNotSupportedError(
                f"converter {chosen!r} does not support {detected.extension!r} files"
            )

        return RoutingDecision(
            target_format=target,
            detected=detected,
            converter_name=chosen,
            converter=converter,
        )

    @property
    def available_converters(self) -> list[str]:
        return sorted(self._registry)

    # ---- internals ----------------------------------------------------
    @staticmethod
    def _classify(input_path: Path, detected: DetectedFormat) -> TargetFormat:
        match detected.extension:
            case ".epub":
                return TargetFormat.epub
            case ".pdf":
                flavour = inspect_pdf(input_path).flavour
                return (
                    TargetFormat.pdf_scanned
                    if flavour == PdfFlavour.scanned
                    else TargetFormat.pdf_native
                )
            case ".docx":
                return TargetFormat.docx
            case ".html":
                return TargetFormat.html
            case ".txt":
                return TargetFormat.txt
            case _:
                raise FormatNotSupportedError(
                    f"no target format for extension {detected.extension!r}"
                )
