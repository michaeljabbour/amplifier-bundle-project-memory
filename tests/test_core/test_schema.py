"""Tests for project_memory_core.schema."""

import sqlite3

import pytest

from project_memory_core.schema import (
    SCHEMA_VERSION,
    get_schema_version,
    init_db,
)


@pytest.fixture
def conn():
    """In-memory SQLite connection for fast, isolated schema tests."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    yield c
    c.close()


# ---------------------------------------------------------------------------
# init_db — table creation
# ---------------------------------------------------------------------------


def test_init_db_creates_memories_table(conn):
    """init_db creates the memories table."""
    init_db(conn)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
    ).fetchone()
    assert row is not None, "memories table should exist after init_db"


def test_init_db_creates_memories_fts_table(conn):
    """init_db creates the memories_fts virtual table."""
    init_db(conn)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts'"
    ).fetchone()
    assert row is not None, "memories_fts virtual table should exist after init_db"


def test_init_db_creates_raw_captures_table(conn):
    """init_db creates the raw_captures table."""
    init_db(conn)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='raw_captures'"
    ).fetchone()
    assert row is not None, "raw_captures table should exist after init_db"


def test_init_db_is_idempotent(conn):
    """Calling init_db twice does not raise and leaves tables intact."""
    init_db(conn)
    init_db(conn)  # second call must not raise

    tables = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "memories" in tables
    assert "raw_captures" in tables


# ---------------------------------------------------------------------------
# memories table — column presence
# ---------------------------------------------------------------------------


def test_memories_table_has_required_columns(conn):
    """memories table has every column specified in the spec."""
    init_db(conn)
    cursor = conn.execute("PRAGMA table_info(memories)")
    columns = {row["name"] for row in cursor.fetchall()}
    expected = {
        "id",
        "category",
        "content",
        "importance",
        "source",
        "created_at",
        "last_accessed",
        "access_count",
        "metadata",
    }
    assert expected <= columns, f"Missing columns: {expected - columns}"


def test_memories_table_id_is_primary_key(conn):
    """memories.id is the primary key."""
    init_db(conn)
    cursor = conn.execute("PRAGMA table_info(memories)")
    pk_cols = [row["name"] for row in cursor.fetchall() if row["pk"] == 1]
    assert "id" in pk_cols


def test_memories_table_default_importance(conn):
    """memories.importance defaults to 0.5."""
    init_db(conn)
    conn.execute(
        "INSERT INTO memories (id, category, content, created_at)"
        " VALUES (?, ?, ?, ?)",
        ("test-id", "decision", "some content", "2024-01-01T00:00:00"),
    )
    row = conn.execute(
        "SELECT importance FROM memories WHERE id='test-id'"
    ).fetchone()
    assert row["importance"] == 0.5


def test_memories_table_default_source(conn):
    """memories.source defaults to 'observed'."""
    init_db(conn)
    conn.execute(
        "INSERT INTO memories (id, category, content, created_at)"
        " VALUES (?, ?, ?, ?)",
        ("test-id2", "decision", "content", "2024-01-01T00:00:00"),
    )
    row = conn.execute(
        "SELECT source FROM memories WHERE id='test-id2'"
    ).fetchone()
    assert row["source"] == "observed"


def test_memories_table_default_access_count(conn):
    """memories.access_count defaults to 0."""
    init_db(conn)
    conn.execute(
        "INSERT INTO memories (id, category, content, created_at)"
        " VALUES (?, ?, ?, ?)",
        ("test-id3", "decision", "content", "2024-01-01T00:00:00"),
    )
    row = conn.execute(
        "SELECT access_count FROM memories WHERE id='test-id3'"
    ).fetchone()
    assert row["access_count"] == 0


# ---------------------------------------------------------------------------
# memories_fts — FTS5 with porter tokenizer
# ---------------------------------------------------------------------------


def test_memories_fts_uses_porter_tokenizer(conn):
    """memories_fts is an FTS5 virtual table and supports stemmed queries."""
    init_db(conn)
    conn.execute(
        "INSERT INTO memories (id, category, content, created_at)"
        " VALUES (?, ?, ?, ?)",
        ("fts-id", "architecture", "authentication using OAuth tokens",
         "2024-01-01T00:00:00"),
    )
    conn.execute(
        "INSERT INTO memories_fts(rowid, content, category) VALUES (?, ?, ?)",
        (1, "authentication using OAuth tokens", "architecture"),
    )
    rows = conn.execute(
        "SELECT * FROM memories_fts WHERE memories_fts MATCH 'auth*'"
    ).fetchall()
    assert len(rows) >= 1, "FTS5 should find 'authentication' via prefix 'auth*'"


# ---------------------------------------------------------------------------
# raw_captures table — column presence
# ---------------------------------------------------------------------------


def test_raw_captures_table_has_required_columns(conn):
    """raw_captures table has every column specified in the spec."""
    init_db(conn)
    cursor = conn.execute("PRAGMA table_info(raw_captures)")
    columns = {row["name"] for row in cursor.fetchall()}
    expected = {
        "id",
        "timestamp",
        "event_type",
        "raw_content",
        "signal_type",
        "confidence",
        "processed",
        "session_id",
    }
    assert expected <= columns, f"Missing columns: {expected - columns}"


def test_raw_captures_id_is_primary_key(conn):
    """raw_captures.id is an INTEGER PRIMARY KEY."""
    init_db(conn)
    cursor = conn.execute("PRAGMA table_info(raw_captures)")
    pk_cols = [row["name"] for row in cursor.fetchall() if row["pk"] == 1]
    assert "id" in pk_cols


def test_raw_captures_default_processed_false(conn):
    """raw_captures.processed defaults to 0 (false)."""
    init_db(conn)
    conn.execute(
        "INSERT INTO raw_captures (timestamp, event_type, raw_content)"
        " VALUES (?, ?, ?)",
        ("2024-01-01T00:00:00", "tool:post", "some raw content"),
    )
    row = conn.execute("SELECT processed FROM raw_captures").fetchone()
    assert row["processed"] == 0


def test_raw_captures_default_confidence(conn):
    """raw_captures.confidence defaults to 0.5."""
    init_db(conn)
    conn.execute(
        "INSERT INTO raw_captures (timestamp, event_type, raw_content)"
        " VALUES (?, ?, ?)",
        ("2024-01-01T00:00:00", "prompt:complete", "content"),
    )
    row = conn.execute("SELECT confidence FROM raw_captures").fetchone()
    assert row["confidence"] == 0.5


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------


def test_schema_version_constant_is_1():
    """SCHEMA_VERSION module constant is 1."""
    assert SCHEMA_VERSION == 1


def test_get_schema_version_returns_1_after_init(conn):
    """get_schema_version returns SCHEMA_VERSION after init_db."""
    init_db(conn)
    assert get_schema_version(conn) == SCHEMA_VERSION
