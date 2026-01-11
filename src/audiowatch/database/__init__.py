"""Database module for AudioWatch.

Provides DuckDB database connection and repository functions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from audiowatch.database.models import Base

if TYPE_CHECKING:
    pass

# Global engine and session factory
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine(database_path: Path | None = None) -> Engine:
    """Get or create the SQLAlchemy engine for DuckDB.

    Args:
        database_path: Optional path to the database file.
                      If None, uses the path from settings.

    Returns:
        SQLAlchemy Engine instance.
    """
    global _engine

    if _engine is not None:
        return _engine

    if database_path is None:
        from audiowatch.config import get_settings

        settings = get_settings()
        database_path = settings.database.path

    # Ensure parent directory exists
    database_path.parent.mkdir(parents=True, exist_ok=True)

    # Create DuckDB engine
    _engine = create_engine(
        f"duckdb:///{database_path}",
        echo=False,
    )

    return _engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Get or create the session factory.

    Args:
        engine: Optional SQLAlchemy engine. If None, uses get_engine().

    Returns:
        Session factory for creating database sessions.
    """
    global _session_factory

    if _session_factory is not None:
        return _session_factory

    if engine is None:
        engine = get_engine()

    _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _session_factory


def get_session() -> Session:
    """Create a new database session.

    Returns:
        A new SQLAlchemy Session instance.
    """
    factory = get_session_factory()
    return factory()


def init_database(engine: Engine | None = None) -> None:
    """Initialize the database by creating all tables.

    Args:
        engine: Optional SQLAlchemy engine. If None, uses get_engine().
    """
    if engine is None:
        engine = get_engine()

    Base.metadata.create_all(engine)


def reset_database(engine: Engine | None = None) -> None:
    """Drop and recreate all tables. USE WITH CAUTION.

    Args:
        engine: Optional SQLAlchemy engine. If None, uses get_engine().
    """
    if engine is None:
        engine = get_engine()

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def close_database() -> None:
    """Close the database connection and reset global state."""
    global _engine, _session_factory

    if _engine is not None:
        _engine.dispose()
        _engine = None

    _session_factory = None


__all__ = [
    "Base",
    "get_engine",
    "get_session",
    "get_session_factory",
    "init_database",
    "reset_database",
    "close_database",
]
