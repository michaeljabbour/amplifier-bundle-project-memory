"""DB schema, migrations, and table definitions for the project memory store."""

import sqlite3

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# DDL constants — kept as module-level strings for testability
# ---------------------------------------------------------------------------

_CREATE_MEMORIES = """
CREATE TABLE IF NOT EXISTS memories (
    id           TEXT PRIMARY KEY,
    category     TEXT NOT NULL,
    content      TEXT NOT NULL,
    importance   REAL    DEFAULT 0.5,
    source       TEXT    DEFAULT 'observed',
    created_at   TEXT NOT NULL,
    last_accessed TEXT,
    access_count INTEGER DEFAULT 0,
    metadata     TEXT
);
"""

_CREATE_MEMORIES_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
    USING fts5(content, category, tokenize='porter');
"""

_CREATE_RAW_CAPTURES = """
CREATE TABLE IF NOT EXISTS raw_captures (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    raw_content TEXT NOT NULL,
    signal_type TEXT,
    confidence  REAL    DEFAULT 0.5,
    processed   INTEGER DEFAULT 0,
    session_id  TEXT
);
"""

_CREATE_SCHEMA_META = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables and seed schema_meta.  Idempotent (IF NOT EXISTS)."""
    conn.execute(_CREATE_MEMORIES)
    conn.execute(_CREATE_MEMORIES_FTS)
    conn.execute(_CREATE_RAW_CAPTURES)
    conn.execute(_CREATE_SCHEMA_META)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        ("version", str(SCHEMA_VERSION)),
    )
    conn.commit()


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the schema version recorded in schema_meta."""
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'version'"
    ).fetchone()
    if row is None:
        return 0
    # sqlite3.Row supports both index and key access
    val = row[0] if not hasattr(row, "keys") else row["value"]
    return int(val)
