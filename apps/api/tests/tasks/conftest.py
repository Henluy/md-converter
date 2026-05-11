"""Fixtures for Celery task tests.

We force eager mode so tasks run synchronously without a broker.
The fixture from ``tests/converters/conftest.py`` (``_build_epub``) is
re-used to produce hermetic input data.
"""

from __future__ import annotations

import os

import pytest

# Eager mode MUST be enabled before celery_app is built/imported.
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")


@pytest.fixture(scope="session", autouse=True)
def _force_eager_celery_app() -> None:
    """Apply eager-mode config to the imported celery_app (singleton)."""
    from app.tasks.celery_app import celery_app

    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        broker_url="memory://",
        result_backend="cache+memory://",
    )
