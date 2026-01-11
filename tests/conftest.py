"""Pytest configuration and fixtures for AudioWatch tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from audiowatch.config import Settings
from audiowatch.database.models import Base


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_db_path(temp_dir: Path) -> Path:
    """Get a temporary database path."""
    return temp_dir / "test.db"


@pytest.fixture
def test_engine(test_db_path: Path):
    """Create a test database engine."""
    engine = create_engine(f"duckdb:///{test_db_path}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_session(test_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with temporary paths."""
    return Settings(
        database={"path": str(temp_dir / "test.db")},
        scraper={
            "poll_interval_minutes": 1,
            "initial_scrape_days": 7,
        },
        logging={"level": "DEBUG"},
    )


@pytest.fixture
def sample_config_yaml(temp_dir: Path) -> Path:
    """Create a sample config.yaml file for testing."""
    config_content = """
scraper:
  poll_interval_minutes: 5
  initial_scrape_days: 30

database:
  path: "{db_path}"

notifications:
  email:
    enabled: false
  discord:
    enabled: false

watch_rules:
  - name: "Test Rule"
    expression: 'title contains "test"'
    notify_via:
      - discord
    enabled: true

logging:
  level: "DEBUG"
  format: "console"
""".format(db_path=str(temp_dir / "test.db"))

    config_path = temp_dir / "config.yaml"
    config_path.write_text(config_content)
    return config_path
