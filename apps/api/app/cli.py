"""Minimal CLI for direct, queue-less conversion.

Usage::

    uv run python -m app.cli --input book.epub --output ./data/output
    uv run python -m app.cli --input book.epub --output ./data/output --override pandoc

Behaviour:
- File is validated (whitelist + libmagic + size) before routing.
- Router picks the right converter based on the detected target format.
- ``--override`` forces a specific registered converter, e.g. Marker on a
  text-native PDF.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app.converters import (
    ConversionError,
    ConverterRouter,
    ConverterUnavailableError,
    FormatNotSupportedError,
    build_default_registry,
)
from app.security import (
    FileTooLargeError,
    FileValidationError,
    validate_upload,
)

logger = logging.getLogger("md-converter.cli")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-converter",
        description="Convert a single document to markdown without queueing.",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        type=Path,
        help="Path to the source file.",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        type=Path,
        help="Output directory; created if missing.",
    )
    parser.add_argument(
        "--override", "-c",
        default=None,
        help="Force a registered converter (overrides routing decision).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Per-file timeout in seconds (default: 300).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # ---- 1. validate ---------------------------------------------------
    try:
        detected = validate_upload(args.input)
    except FileTooLargeError as exc:
        logger.error("Rejected: %s", exc)
        return 5
    except FileValidationError as exc:
        logger.error("Rejected: %s", exc)
        return 5

    logger.debug(
        "validated input=%s ext=%s mime=%s size=%d",
        args.input, detected.extension, detected.mime_type, detected.size_bytes,
    )

    # ---- 2. route -----------------------------------------------------
    router = ConverterRouter(build_default_registry())
    try:
        decision = router.resolve(args.input, override=args.override)
    except FormatNotSupportedError as exc:
        logger.error("Unsupported input: %s", exc)
        return 3

    logger.info(
        "routed target=%s converter=%s",
        decision.target_format, decision.converter_name,
    )

    # ---- 3. convert ---------------------------------------------------
    try:
        result = decision.converter.convert(args.input, args.output)
    except ConverterUnavailableError as exc:
        logger.error("Converter unavailable: %s", exc)
        return 2
    except ConversionError as exc:
        logger.error("Conversion failed: %s", exc)
        if exc.stderr:
            logger.debug("stderr: %s", exc.stderr.strip())
        return 4

    logger.info(
        "✔ %s → %s (%s bytes, %.2fs)",
        args.input.name,
        result.output_path,
        result.size_bytes,
        result.duration_seconds,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
