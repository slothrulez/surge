"""Database engine and session factory (Phase 2, Task 30).

Connection pooling is configured from DATABASE_URL at first use. Importing
this module never connects to a database.
"""

import logging
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def create_database_engine(database_url: str) -> Engine:
    """Create a pooled engine with pre-ping validation.

    Args:
        database_url: PostgreSQL connection URL.

    Returns:
        Configured SQLAlchemy engine.

    Raises:
        RuntimeError: If URL dialect is not PostgreSQL.
    """
    if make_url(database_url).get_backend_name() != "postgresql":
        raise RuntimeError("DATABASE_URL must be a PostgreSQL URL")
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
    )


def get_engine(database_url: str | None = None) -> Engine:
    """Return the process-wide engine, creating it once if needed."""
    global _engine
    if _engine is None:
        if database_url is None:
            raise RuntimeError(
                "Engine not initialized; call init_engine first"
            )
        _engine = create_database_engine(database_url)
    return _engine


def init_engine(database_url: str) -> Engine:
    """Initialize the global engine and session factory.

    Args:
        database_url: PostgreSQL connection URL.

    Returns:
        The newly created engine.
    """
    global _engine, _session_factory
    _engine = create_database_engine(database_url)
    _session_factory = sessionmaker(
        bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False
    )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the session factory bound to the initialized engine."""
    if _session_factory is None:
        raise RuntimeError("Engine not initialized; call init_engine first")
    return _session_factory


def get_db() -> Iterator[Session]:
    """Yield a database session, always closing it afterwards."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def dispose_engine() -> None:
    """Dispose pooled connections and reset engine state."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
