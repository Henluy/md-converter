"""Celery application factory.

Conversion tasks live in ``app.tasks.conversion`` and are auto-imported
through the include list. Settings come from ``app.config.Settings`` so
the same .env at the repo root configures API and worker alike.
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings


def make_celery() -> Celery:
    settings = get_settings()

    app = Celery(
        "md-converter",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.tasks.conversion"],
    )

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=50,
        broker_connection_retry_on_startup=True,
        result_expires=3600 * 24,
        task_soft_time_limit=settings.celery_task_soft_time_limit,
        task_time_limit=settings.celery_task_time_limit,
        # Toggled to True in unit tests via Settings/env.
        task_always_eager=settings.celery_task_always_eager,
        task_eager_propagates=settings.celery_task_always_eager,
    )

    return app


celery_app = make_celery()
