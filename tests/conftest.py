"""Shared test fixtures for project-memory test suite."""

import sqlite3
import sys
import types
from pathlib import Path

import pytest

# Add all module source directories to sys.path for direct imports
MODULES_DIR = Path(__file__).parent.parent / "modules"
for module_dir in MODULES_DIR.iterdir():
    if module_dir.is_dir():
        sys.path.insert(0, str(module_dir))

# Provide a lightweight amplifier_core shim when the Amplifier runtime is not
# installed.  The only symbol the tool module needs is ToolResult — a simple
# data container.  This lets the full test suite run without amplifier-core.
if "amplifier_core" not in sys.modules:
    try:
        import amplifier_core  # noqa: F401
    except ModuleNotFoundError:
        _shim = types.ModuleType("amplifier_core")

        class _ToolResult:
            """Minimal stand-in for amplifier_core.ToolResult."""

            __slots__ = ("success", "output")

            def __init__(self, *, success: bool, output):
                self.success = success
                self.output = output

            def __repr__(self):
                return f"ToolResult(success={self.success!r}, output={self.output!r})"

        _shim.ToolResult = _ToolResult  # type: ignore[attr-defined]
        sys.modules["amplifier_core"] = _shim


@pytest.fixture
def memory_db():
    """In-memory SQLite database for fast tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
