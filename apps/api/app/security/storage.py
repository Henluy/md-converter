"""Storage path-traversal defence (BRIEF §10).

Every path coming from user-controlled state (DB rows, multipart uploads,
CLI arguments) must be funnelled through :func:`safe_resolve_relative`
before touching the filesystem. We never trust that ``storage_path`` and
friends are well-formed — we resolve them and assert they stay inside
``settings.data_dir``.
"""

from __future__ import annotations

from pathlib import Path


class PathTraversalError(Exception):
    """Raised when a resolved path escapes the allowed base directory."""


def safe_resolve_relative(base: Path, relative_path: str | Path) -> Path:
    """Resolve ``relative_path`` against ``base`` and enforce containment.

    Rules:
      - The input MUST be relative (absolute paths are rejected outright).
      - After ``Path.resolve(strict=False)`` the result MUST be a descendant
        of ``base.resolve(strict=False)``.
      - Symlinks are resolved before the comparison so a symlinked-out
        target cannot smuggle a traversal past the check.

    Returns the absolute, resolved path. Callers should still confirm
    existence with ``.exists()`` when they need it.
    """
    rel = Path(relative_path)
    if rel.is_absolute():
        raise PathTraversalError(
            f"absolute paths are not allowed (got {rel!s})"
        )

    base_resolved = base.resolve(strict=False)
    candidate = (base_resolved / rel).resolve(strict=False)

    if not candidate.is_relative_to(base_resolved):
        raise PathTraversalError(
            f"resolved path {candidate!s} escapes base {base_resolved!s}"
        )

    return candidate
