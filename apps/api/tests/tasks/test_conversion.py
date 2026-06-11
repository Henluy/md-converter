"""Celery task tests in eager mode against a real local Postgres.

Skips automatically when DATABASE_URL still points to the test placeholder
(see :func:`_has_database` in the root conftest).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.config import get_settings
from app.models.db import JobStatus
from app.security import MimeTypeMismatchError
from app.services import NewFileSpec, create_job, get_file, get_job
from app.tasks import convert_file_task

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _stage(spec_dir: Path, source: Path) -> tuple[Path, str]:
    """Copy ``source`` into ``spec_dir/input/{uuid}{suffix}`` and return paths."""
    stem = source.stem
    stored = f"{uuid4().hex}_{stem}{source.suffix}"
    inp = spec_dir / "input"
    inp.mkdir(parents=True, exist_ok=True)
    target = inp / stored
    target.write_bytes(source.read_bytes())
    relative = f"input/{stored}"
    return target, relative


@pytest.fixture
def override_data_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    """Point settings.data_dir at tmp_path (clears the lru_cache)."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.mark.usefixtures("skip_if_no_pandoc")
def test_task_full_pipeline_epub(
    db_session_sync: Session,
    override_data_dir: Path,
    epub_file: Path,
) -> None:
    """End-to-end: create job → dispatch task → file_row + job updated."""
    staged, relative = _stage(override_data_dir, epub_file)

    job = create_job(
        db_session_sync,
        [
            NewFileSpec(
                original_filename=epub_file.name,
                stored_filename=staged.name,
                original_format=".epub",
                storage_path=relative,
                size_bytes=staged.stat().st_size,
            )
        ],
    )
    db_session_sync.commit()
    file_id = job.files[0].id

    result = convert_file_task.apply(kwargs={"file_id": str(file_id)})
    assert result.successful()
    payload = result.result

    assert payload["converter"] == "pandoc"
    assert payload["target_format"] == "epub"
    assert payload["file_id"] == str(file_id)
    assert payload["job_id"] == str(job.id)

    # Reload via a fresh session (task committed in its own txn).
    db_session_sync.expire_all()
    refreshed = get_job(db_session_sync, job.id)
    assert refreshed is not None
    assert refreshed.status == JobStatus.done.value
    assert refreshed.processed_files == 1
    assert refreshed.completed_at is not None

    file_after = get_file(db_session_sync, file_id)
    assert file_after is not None
    assert file_after.converter_used == "pandoc"
    assert file_after.output_path is not None
    assert file_after.output_path.startswith(f"output/{job.id}")


def test_task_unknown_file_id_raises(
    db_session_sync: Session,
    override_data_dir: Path,
) -> None:
    del db_session_sync, override_data_dir  # only needed to enforce DB + env setup
    bogus = uuid4()
    with pytest.raises(LookupError):
        convert_file_task.apply(kwargs={"file_id": str(bogus)})


def test_task_failed_file_marks_job_failed(
    db_session_sync: Session,
    override_data_dir: Path,
    tmp_path: Path,
) -> None:
    """An unsupported file → task fails AND job row records failure."""
    # Spoofed extension (plain text claiming to be a PDF)
    rogue = tmp_path / "trash.pdf"
    rogue.write_bytes(b"definitely not a real pdf")
    staged, relative = _stage(override_data_dir, rogue)

    job = create_job(
        db_session_sync,
        [
            NewFileSpec(
                original_filename=rogue.name,
                stored_filename=staged.name,
                original_format=".pdf",
                storage_path=relative,
                size_bytes=staged.stat().st_size,
            )
        ],
    )
    db_session_sync.commit()
    file_id = job.files[0].id

    with pytest.raises(MimeTypeMismatchError):
        convert_file_task.apply(kwargs={"file_id": str(file_id)})

    db_session_sync.expire_all()
    refreshed = get_job(db_session_sync, job.id)
    assert refreshed is not None
    # Single-file job, that file failed → the whole job is failed.
    assert refreshed.status == JobStatus.failed.value
    assert refreshed.completed_at is not None

    # The detailed reason now lives on the file row (per-file error tracking).
    file_after = get_file(db_session_sync, file_id)
    assert file_after is not None
    assert file_after.status == "failed"
    assert file_after.error_message is not None
    assert "MimeTypeMismatch" in file_after.error_message
