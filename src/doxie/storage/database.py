"""Database utilities for SQLAlchemy 2.x.

Provides engine/session factories and a convenient session scope context manager.
PostgreSQL-only (via psycopg driver).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from . import models


def get_engine(url: str, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine for PostgreSQL using the psycopg driver.

    Parameters
    ----------
    url:
        SQLAlchemy URL. Must be a PostgreSQL URL, e.g. "postgresql+psycopg://user:pass@host/db".
        If provided as "postgresql://...", it will be normalized to use the psycopg driver.
    echo:
        If True, SQL statements are logged to stdout (useful for debugging).
    """
    # Enforce PostgreSQL-only and normalize driver to psycopg
    if url.startswith("sqlite"):
        raise ValueError("SQLite is not supported in this configuration. Use PostgreSQL.")

    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    elif not url.startswith("postgresql+psycopg://"):
        raise ValueError("Unsupported database URL. Expected 'postgresql+psycopg://'.")

    # Enable pre-ping to gracefully handle stale/disconnected connections
    return create_engine(url, echo=echo, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a sessionmaker bound to the provided engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations.

    Commits on success, rolls back on error, and always closes the session.
    """
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(engine: Engine) -> None:
    """Create database tables based on SQLAlchemy models if they do not exist."""
    models.Base.metadata.create_all(bind=engine)
