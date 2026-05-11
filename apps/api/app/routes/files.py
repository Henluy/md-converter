"""File-content endpoint — serves the generated markdown for preview.

Path traversal defence in depth: we resolve the on-disk path with
:func:`safe_resolve_relative` against ``settings.data_dir`` even though
the stored ``output_path`` is supposed to live inside it.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.db_sync import sync_session_scope
from app.security import PathTraversalError, safe_resolve_relative
from app.services import get_file

router = APIRouter(prefix="/files", tags=["files"])


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
