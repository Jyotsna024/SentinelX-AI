"""
conftest.py — SentinelX AI Phase 2 Tests Configuration
=========================================================
Pytest fixtures and configuration. Configures FastAPI dependency overrides
to mock the database session, avoiding any live PostgreSQL network requirements.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import FastAPI app
from backend.main import app
from backend.db.session import get_db


# ── Database Session Mock Fixture ──────────────────────────────────────────────
@pytest.fixture
def mock_db() -> MagicMock:
    """
    Return a mock database session.

    Mocks basic SQLAlchemy methods (add, commit, rollback, query)
    so routers can run database operations without real connectivity.
    """
    db_session = MagicMock()
    return db_session


# ── Test Client Fixture ────────────────────────────────────────────────────────
@pytest.fixture
def client(mock_db: MagicMock) -> TestClient:
    """
    Return a TestClient bound to the FastAPI app with mocked database dependencies.
    """
    # Override get_db dependency to yield the mocked database session
    def _override_get_db():
        try:
            yield mock_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    # Construct the TestClient
    with TestClient(app) as test_client:
        yield test_client

    # Clear dependency overrides after tests finish
    app.dependency_overrides.clear()
