"""Integration tests for app.services.jobs against a real Postgres."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.converters import ConversionResult
from app.models.db import JobStatus
from app.services import (
    JobValidationError,
    NewFileSpec,
    complete_file,
    create_job,
    fail_file,
    get_file,
    get_job,
    recompute_job_status,
    start_file,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _spec(name: str = "book.epub") -> NewFileSpec:
    return NewFileSpec(
        original_filename=name,
        stored_filename=f"{uuid4().hex}_{name}",
        original_format=".epub",
        storage_path=f"input/{uuid4().hex}_{name}",
        size_bytes=1234,
    )


def test_create_job_persists_rows(db_session_sync: Session) -> None:
    job = create_job(db_session_sync, [_spec(), _spec()])

    assert job.id is not None
    assert job.status == JobStatus.pending.value
    assert job.total_files == 2
    assert job.processed_files == 0
    assert len(job.files) == 2

    # round-trip via the session
    fetched = get_job(db_session_sync, job.id)
    assert fetched is not None
    assert fetched.total_files == 2


def test_create_job_rejects_empty_files(db_session_sync: Session) -> None:
    with pytest.raises(ValueError):
        create_job(db_session_sync, [])


def test_create_job_rejects_too_many_files(
    db_session_sync: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A batch above ``max_files_per_job`` is refused before any row is written."""
    from app.config import get_settings

    monkeypatch.setenv("MAX_FILES_PER_JOB", "3")
    get_settings.cache_clear()
    try:
        with pytest.raises(JobValidationError):
            create_job(db_session_sync, [_spec() for _ in range(4)])
    finally:
        get_settings.cache_clear()


def test_create_job_rejects_oversized_batch(
    db_session_sync: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sum of file sizes above ``max_job_size_mb`` is refused."""
    from app.config import get_settings

    monkeypatch.setenv("MAX_JOB_SIZE_MB", "1")  # 1 MB limit
    get_settings.cache_clear()
    try:
        big = NewFileSpec(
            original_filename="huge.pdf",
            stored_filename=f"{uuid4().hex}_huge.pdf",
            original_format=".pdf",
            storage_path=f"input/{uuid4().hex}_huge.pdf",
            size_bytes=2 * 1024 * 1024,  # 2 MB
        )
        with pytest.raises(JobValidationError):
            create_job(db_session_sync, [big])
    finally:
        get_settings.cache_clear()


def test_start_file_marks_job_processing(db_session_sync: Session) -> None:
    job = create_job(db_session_sync, [_spec()])
    file_id = job.files[0].id

    start_file(db_session_sync, file_id)
    db_session_sync.flush()

    fetched = get_job(db_session_sync, job.id)
    assert fetched is not None
    assert fetched.status == JobStatus.processing.value


def test_complete_file_records_output_and_increments(
    db_session_sync: Session,
    tmp_path: Path,
) -> None:
    job = create_job(db_session_sync, [_spec(), _spec()])
    f1, f2 = job.files

    @dataclass(frozen=True, slots=True)
    class _Result:
        output_path: Path
        converter: str
        pages: int | None
        size_bytes: int
        duration_seconds: float
        warnings: list[str]

    res = ConversionResult(
        output_path=tmp_path / "output" / "x.md",
        converter="pandoc",
        pages=12,
        size_bytes=2048,
        duration_seconds=0.42,
    )

    complete_file(
        db_session_sync,
        f1.id,
        res,
        converter_name="pandoc",
        output_relative_path="output/x.md",
    )
    db_session_sync.flush()

    file_row = get_file(db_session_sync, f1.id)
    assert file_row is not None
    assert file_row.output_path == "output/x.md"
    assert file_row.converter_used == "pandoc"
    assert file_row.size_bytes == 2048
    assert file_row.pages == 12

    job_after = get_job(db_session_sync, job.id)
    assert job_after is not None
    assert job_after.processed_files == 1

    # Job not done yet — there's still f2 pending
    status = recompute_job_status(db_session_sync, job.id)
    assert status != JobStatus.done

    # Finish the second file → job flips to done
    complete_file(
        db_session_sync,
        f2.id,
        res,
        converter_name="pandoc",
        output_relative_path="output/y.md",
    )
    db_session_sync.flush()
    status = recompute_job_status(db_session_sync, job.id)
    assert status == JobStatus.done

    final = get_job(db_session_sync, job.id)
    assert final is not None
    assert final.status == JobStatus.done.value
    assert isinstance(final.completed_at, datetime)


def test_fail_file_marks_only_the_file(db_session_sync: Session) -> None:
    """fail_file records the per-file failure but doesn't condemn the job —
    other files may still succeed (→ partial_success)."""
    job = create_job(db_session_sync, [_spec(), _spec()])
    f1 = job.files[0]
    fail_file(db_session_sync, f1.id, error_message="boom")
    db_session_sync.flush()

    file_row = get_file(db_session_sync, f1.id)
    assert file_row is not None
    assert file_row.status == "failed"
    assert file_row.error_message == "boom"

    # f2 is still pending → the job is not terminal yet.
    status = recompute_job_status(db_session_sync, job.id)
    assert status == JobStatus.processing


def test_recompute_all_failed_is_failed(db_session_sync: Session) -> None:
    job = create_job(db_session_sync, [_spec()])
    fail_file(db_session_sync, job.files[0].id, error_message="boom")
    db_session_sync.flush()

    status = recompute_job_status(db_session_sync, job.id)
    assert status == JobStatus.failed

    fetched = get_job(db_session_sync, job.id)
    assert fetched is not None
    assert fetched.status == JobStatus.failed.value
    assert fetched.completed_at is not None


def test_recompute_mixed_outcome_is_partial_success(
    db_session_sync: Session,
    tmp_path: Path,
) -> None:
    job = create_job(db_session_sync, [_spec(), _spec()])
    f1, f2 = job.files
    res = ConversionResult(
        output_path=tmp_path / "output" / "x.md",
        converter="pandoc",
        pages=3,
        size_bytes=1024,
        duration_seconds=0.1,
    )
    complete_file(
        db_session_sync,
        f1.id,
        res,
        converter_name="pandoc",
        output_relative_path="output/x.md",
    )
    fail_file(db_session_sync, f2.id, error_message="boom")
    db_session_sync.flush()

    status = recompute_job_status(db_session_sync, job.id)
    assert status == JobStatus.partial_success

    fetched = get_job(db_session_sync, job.id)
    assert fetched is not None
    assert fetched.status == JobStatus.partial_success.value
    assert fetched.completed_at is not None
