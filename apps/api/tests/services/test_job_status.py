"""Unit tests for the pure job-status decision (no DB needed)."""

from __future__ import annotations

from app.models.db import JobStatus
from app.services import compute_job_status


def test_all_files_succeeded_is_done() -> None:
    assert compute_job_status(total=3, succeeded=3, failed=0) == JobStatus.done


def test_all_files_failed_is_failed() -> None:
    assert compute_job_status(total=3, succeeded=0, failed=3) == JobStatus.failed


def test_some_succeeded_some_failed_is_partial_success() -> None:
    assert (
        compute_job_status(total=3, succeeded=2, failed=1)
        == JobStatus.partial_success
    )


def test_not_all_processed_is_processing() -> None:
    assert compute_job_status(total=3, succeeded=1, failed=0) == JobStatus.processing


def test_zero_total_is_pending() -> None:
    assert compute_job_status(total=0, succeeded=0, failed=0) == JobStatus.pending
