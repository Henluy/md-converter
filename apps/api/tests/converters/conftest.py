"""Converter-specific fixtures.

Shared EPUB/output fixtures live in the root tests/conftest.py.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


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
