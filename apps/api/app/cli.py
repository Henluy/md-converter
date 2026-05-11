"""Minimal CLI for direct, queue-less conversion (ticket 5 scope).

Usage::

    uv run python -m app.cli --input book.epub --output ./data/output
    uv run python -m app.cli --input book.epub --output ./data/output --converter pandoc

Once the queue lands (ticket 6) this stays useful for ad-hoc tests and
batch scripts.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from pathlib import Path

from app.converters import (
    BaseConverter,
    ConversionError,
    ConverterUnavailableError,
    FormatNotSupportedError,
    PandocConverter,
)

logger = logging.getLogger("md-converter.cli")

ConverterFactory = Callable[[int], BaseConverter]

# Registry of factories — each takes (timeout_seconds) → BaseConverter.
# Extended at tickets 7-8 (pymupdf, marker, markitdown).
_CONVERTERS: dict[str, ConverterFactory] = {
    "pandoc": lambda timeout: PandocConverter(timeout_seconds=timeout),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-converter",
        description="Convert a single document to markdown without queueing.",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        type=Path,
        help="Path to the source file (EPUB for now).",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        type=Path,
        help="Output directory; created if missing.",
    )
    parser.add_argument(
        "--converter", "-c",
        choices=sorted(_CONVERTERS),
        default="pandoc",
        help="Converter to use (default: pandoc).",
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

    converter = _CONVERTERS[args.converter](args.timeout)

    try:
        result = converter.convert(args.input, args.output)
    except ConverterUnavailableError as exc:
        logger.error("Converter unavailable: %s", exc)
        return 2
    except FormatNotSupportedError as exc:
        logger.error("Unsupported input: %s", exc)
        return 3
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
