"""HTTP integration tests for /api/jobs.

These talk to the real local Postgres; pytest skips them automatically
when DATABASE_URL still points to the test placeholder.
"""

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
async def test_post_jobs_creates_job_and_persists_files(
    client: AsyncClient,
    epub_file: Path,
) -> None:
    """Happy path: one EPUB → job created with one file row."""
    with epub_file.open("rb") as fh:
        response = await client.post(
            "/api/jobs",
            files={"files": (epub_file.name, fh.read(), "application/epub+zip")},
        )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] in {"pending", "processing", "done"}
    assert payload["total_files"] == 1
    assert len(payload["files"]) == 1
    assert payload["files"][0]["original_filename"] == epub_file.name


@pytest.mark.usefixtures("db_session_sync", "override_data_dir")
async def test_post_jobs_rejects_unsupported_extension(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    rogue = tmp_path / "weird.xyz"
    rogue.write_bytes(b"hello")
    with rogue.open("rb") as fh:
        response = await client.post(
            "/api/jobs",
            files={"files": (rogue.name, fh.read(), "application/octet-stream")},
        )

    assert response.status_code == 400
    assert "extension" in response.json()["detail"].lower()


@pytest.mark.usefixtures("db_session_sync", "override_data_dir")
async def test_post_jobs_rejects_spoofed_pdf(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    spoof = tmp_path / "fake.pdf"
    spoof.write_bytes(b"definitely not a pdf")
    with spoof.open("rb") as fh:
        response = await client.post(
            "/api/jobs",
            files={"files": (spoof.name, fh.read(), "application/pdf")},
        )

    assert response.status_code == 400
    assert "mime" in response.json()["detail"].lower() or "libmagic" in response.json()["detail"].lower()


@pytest.mark.usefixtures("db_session_sync", "override_data_dir", "skip_if_no_pandoc")
async def test_get_job_returns_persisted_state(
    client: AsyncClient,
    epub_file: Path,
) -> None:
    with epub_file.open("rb") as fh:
        post = await client.post(
            "/api/jobs",
            files={"files": (epub_file.name, fh.read(), "application/epub+zip")},
        )
    assert post.status_code == 201
    job_id = post.json()["id"]

    get = await client.get(f"/api/jobs/{job_id}")
    assert get.status_code == 200
    payload = get.json()
    assert payload["id"] == job_id
    assert payload["total_files"] == 1


async def test_get_unknown_job_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code in {404, 503}  # 503 if DB unreachable


async def test_post_jobs_rejects_empty_payload(client: AsyncClient) -> None:
    response = await client.post("/api/jobs")
    assert response.status_code in {400, 422}
