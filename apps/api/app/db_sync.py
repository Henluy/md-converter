"""Synchronous SQLAlchemy engine + session factory.

Celery tasks run inside a blocking process, so the worker uses this sync
engine (psycopg 3.x) instead of asyncpg. Schema migrations remain owned by
Drizzle in apps/web/drizzle.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def build_sync_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.sync_database_url,
        echo=False,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
        future=True,
    )


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_sync_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = build_sync_engine()
    return _engine


def get_sync_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            get_sync_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@contextmanager
def sync_session_scope() -> Iterator[Session]:
    """Commit on clean exit, roll back on exception."""
    factory = get_sync_session_factory()
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def dispose_sync_engine() -> None:
    """Close the engine — call this on worker shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
