"""
session.py — SentinelX AI Phase 2
===================================
SQLAlchemy session factory with lazy engine initialisation.

Connection details are read exclusively from the DATABASE_URL environment
variable — no credentials are hardcoded anywhere in this module.

Example DATABASE_URL:
    postgresql://sentinelx:secret@localhost:5432/sentinelx_db

Usage (FastAPI dependency injection):
    from backend.db.session import get_db

    @router.get("/foo")
    def foo(db: Session = Depends(get_db)):
        ...
"""

import logging
import os
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# ── Module-level singletons (lazily initialised) ───────────────────────────────
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None  # type: ignore[type-arg]


def _get_database_url() -> str:
    """
    Read the DATABASE_URL from environment variables.
    Falls back to a local SQLite database if not configured.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        logger.warning("DATABASE_URL environment variable is not set. Falling back to local sqlite:///sentinelx.db")
        return "sqlite:///sentinelx.db"
    return url


def get_engine() -> Engine:
    """
    Return the SQLAlchemy engine, creating it on first call.

    Uses pool_pre_ping=True to detect and recycle stale connections
    gracefully without crashing on first use after a DB restart.

    Returns:
        The singleton SQLAlchemy Engine instance.

    Raises:
        RuntimeError: If DATABASE_URL is not configured.
    """
    global _engine
    if _engine is None:
        db_url = _get_database_url()
        logger.info("Creating database engine (pool_pre_ping=True)...")
        _engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
        logger.info("Database engine created successfully.")
    return _engine


def get_session_factory() -> sessionmaker:  # type: ignore[type-arg]
    """
    Return the SQLAlchemy sessionmaker, creating it on first call.

    Returns:
        The singleton sessionmaker bound to the engine.
    """
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency: yield a database session, always closing it on teardown.

    Usage:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...

    Yields:
        A SQLAlchemy Session instance.
    """
    SessionLocal = get_session_factory()
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_connection() -> bool:
    """
    Verify that the database is reachable. Intended for health-check use.

    Returns:
        True if connection succeeds, False otherwise.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error(f"Database connectivity check failed: {exc}")
        return False
