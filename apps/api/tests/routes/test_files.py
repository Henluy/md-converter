"""HTTP integration tests for /api/files/{file_id}/content."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

from app.config import get_settings


@pytest.fixture
def override_data_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "true")
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.mark.usefixtures("db_session_sync", "override_data_dir", "skip_if_no_pandoc")
async def test_file_content_returns_markdown(
    client: AsyncClient,
    epub_file: Path,
) -> None:
    """Upload + convert + GET content → returns text/markdown."""
    with epub_file.open("rb") as fh:
        post = await client.post(
            "/api/jobs",
            files={"files": (epub_file.name, fh.read(), "application/epub+zip")},
        )
    assert post.status_code == 201
    job = post.json()
    file_id = job["files"][0]["id"]

    response = await client.get(f"/api/files/{file_id}/content")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "Chapter One" in response.text


@pytest.mark.usefixtures("db_session_sync")
async def test_file_content_unknown_id_returns_404(client: AsyncClient) -> None:
    response = await client.get(
        "/api/files/00000000-0000-0000-0000-000000000000/content"
    )
    assert response.status_code == 404


@pytest.mark.usefixtures("db_session_sync", "override_data_dir", "skip_if_no_pandoc")
async def test_file_content_409_when_not_yet_converted(
    client: AsyncClient,
    db_session_sync,
    tmp_path: Path,
) -> None:
    """A file row without ``output_path`` returns 409."""
    from uuid import uuid4

    from app.services import NewFileSpec, create_job

    spec = NewFileSpec(
        original_filename="book.epub",
        stored_filename=f"{uuid4().hex}_book.epub",
        original_format=".epub",
        storage_path=f"input/{uuid4().hex}_book.epub",
        size_bytes=42,
    )
    job = create_job(db_session_sync, [spec])
    db_session_sync.commit()
    file_id = job.files[0].id

    response = await client.get(f"/api/files/{file_id}/content")
    assert response.status_code == 409


@pytest.mark.usefixtures("db_session_sync", "override_data_dir", "skip_if_no_pandoc")
async def test_file_download_sets_attachment_header(
    client: AsyncClient,
    epub_file: Path,
) -> None:
    with epub_file.open("rb") as fh:
        post = await client.post(
            "/api/jobs",
            files={"files": (epub_file.name, fh.read(), "application/epub+zip")},
        )
    assert post.status_code == 201
    file_id = post.json()["files"][0]["id"]

    response = await client.get(f"/api/files/{file_id}/download")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert 'attachment; filename="sample.md"' in disposition or "attachment" in disposition
    assert "Chapter One" in response.text


@pytest.mark.usefixtures("db_session_sync", "override_data_dir", "skip_if_no_pandoc")
async def test_job_zip_download_streams_archive(
    client: AsyncClient,
    epub_file: Path,
) -> None:
    import io
    import zipfile

    # Upload two EPUBs in the same job to verify multi-file zip
    with epub_file.open("rb") as fh:
        payload = fh.read()
    response = await client.post(
        "/api/jobs",
        files=[
            ("files", ("alpha.epub", payload, "application/epub+zip")),
            ("files", ("beta.epub", payload, "application/epub+zip")),
        ],
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    zip_response = await client.get(f"/api/jobs/{job_id}/download")
    assert zip_response.status_code == 200
    assert zip_response.headers["content-type"] == "application/zip"
    assert f'md-converter-{job_id}.zip' in zip_response.headers["content-disposition"]

    archive = zipfile.ZipFile(io.BytesIO(zip_response.content))
    names = archive.namelist()
    assert len(names) == 2
    assert {"alpha.md", "beta.md"} == set(names)


@pytest.mark.usefixtures("db_session_sync")
async def test_job_zip_unknown_returns_404(client: AsyncClient) -> None:
    response = await client.get(
        "/api/jobs/00000000-0000-0000-0000-000000000000/download"
    )
    assert response.status_code == 404
