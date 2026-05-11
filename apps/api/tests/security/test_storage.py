"""Path-traversal defence (BRIEF §10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.security import PathTraversalError, safe_resolve_relative


def test_allows_normal_relative_path(tmp_path: Path) -> None:
    resolved = safe_resolve_relative(tmp_path, "input/sub/file.pdf")
    assert resolved.is_relative_to(tmp_path.resolve())
    assert resolved.name == "file.pdf"


def test_rejects_dotdot_traversal(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_resolve_relative(tmp_path, "../../etc/passwd")


def test_rejects_nested_dotdot_traversal(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_resolve_relative(tmp_path, "input/../../escape.txt")


def test_rejects_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_resolve_relative(tmp_path, "/etc/passwd")


def test_rejects_symlink_pointing_outside(tmp_path: Path) -> None:
    """A symlink that resolves outside the base must be rejected."""
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        link = tmp_path / "link.txt"
        link.symlink_to(outside)
        with pytest.raises(PathTraversalError):
            safe_resolve_relative(tmp_path, "link.txt")
    finally:
        outside.unlink(missing_ok=True)


def test_idempotent_when_passed_a_path(tmp_path: Path) -> None:
    resolved = safe_resolve_relative(tmp_path, Path("a/b/c.epub"))
    assert resolved == (tmp_path / "a" / "b" / "c.epub").resolve()
