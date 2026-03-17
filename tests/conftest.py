"""Shared test fixtures for project-memory test suite."""

import sqlite3
import sys
from pathlib import Path

import pytest

# Add all module source directories to sys.path for direct imports
MODULES_DIR = Path(__file__).parent.parent / "modules"
for module_dir in MODULES_DIR.iterdir():
    if module_dir.is_dir():
        sys.path.insert(0, str(module_dir))


@pytest.fixture
def memory_db():
    """In-memory SQLite database for fast tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
