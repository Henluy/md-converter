"""File-content endpoint — serves the generated markdown for preview.

Path traversal defence in depth: we resolve the on-disk path with
:func:`safe_resolve_relative` against ``settings.data_dir`` even though
the stored ``output_path`` is supposed to live inside it.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, PlainTextResponse

from app.config import get_settings
from app.converters.base import sanitise_filename
from app.db_sync import sync_session_scope
from app.security import PathTraversalError, safe_resolve_relative
from app.services import get_file

router = APIRouter(prefix="/files", tags=["files"])

# Output extension → HTTP media type. Imports produce markdown; exports produce
# the binary document formats.
_MEDIA_TYPES: dict[str, str] = {
    ".md": "text/markdown; charset=utf-8",
    ".markdown": "text/markdown; charset=utf-8",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".epub": "application/epub+zip",
}
_MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})


def _media_type_for(suffix: str) -> str:
    return _MEDIA_TYPES.get(suffix.lower(), "application/octet-stream")


@router.get(
    "/{file_id}/content",
    response_class=PlainTextResponse,
    summary="Return the generated markdown for one file",
)
async def get_file_content_route(file_id: UUID) -> PlainTextResponse:
    settings = get_settings()
    with sync_session_scope() as session:
        file_row = get_file(session, file_id)
        if file_row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
        if not file_row.output_path:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "file has not been converted yet",
            )
        # Inline text preview only makes sense for markdown; exported PDFs/
        # DOCX/EPUBs are binary and must be downloaded instead.
        if Path(file_row.output_path).suffix.lower() not in _MARKDOWN_SUFFIXES:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "preview is only available for markdown output; download instead",
            )
        try:
            absolute = safe_resolve_relative(settings.data_dir, file_row.output_path)
        except PathTraversalError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"invalid stored path: {exc}"
            ) from exc

    if not absolute.exists() or not absolute.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "output file missing on disk"
        )

    text = absolute.read_text(encoding="utf-8")
    return PlainTextResponse(
        text,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": "private, max-age=0, must-revalidate",
            "Content-Disposition": f'inline; filename="{absolute.name}"',
        },
    )


@router.get(
    "/{file_id}/download",
    response_class=FileResponse,
    summary="Download the generated markdown as an attachment",
)
async def download_file_route(file_id: UUID) -> FileResponse:
    settings = get_settings()
    with sync_session_scope() as session:
        file_row = get_file(session, file_id)
        if file_row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
        if not file_row.output_path:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "file has not been converted yet"
            )
        try:
            absolute = safe_resolve_relative(settings.data_dir, file_row.output_path)
        except PathTraversalError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"invalid stored path: {exc}"
            ) from exc
        original_stem = Path(file_row.original_filename).stem
        output_suffix = Path(file_row.output_path).suffix or ".md"

    if not absolute.exists() or not absolute.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "output file missing on disk")

    # Attachment name keeps the original (sanitised) stem + the real output
    # extension (.md for imports, .pdf/.docx/.epub for exports).
    download_name = f"{sanitise_filename(original_stem)}{output_suffix}"

    return FileResponse(
        path=str(absolute),
        media_type=_media_type_for(output_suffix),
        filename=download_name,
        headers={"Cache-Control": "private, max-age=0, must-revalidate"},
    )
