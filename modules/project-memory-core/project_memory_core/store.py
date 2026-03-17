"""MemoryStore class providing SQLite + FTS5 operations for project memory."""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project_memory_core.schema import init_db


def _utcnow() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


class MemoryStore:
    """SQLite-backed store for project memory entries and raw captures."""

    def __init__(self, db_path: str | Path) -> None:
        path = str(db_path)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        # WAL mode for concurrent read safety
        self._conn.execute("PRAGMA journal_mode=WAL")
        init_db(self._conn)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    # ------------------------------------------------------------------
    # CRUD — memories
    # ------------------------------------------------------------------

    def create_memory(
        self,
        category: str,
        content: str,
        importance: float,
        source: str,
        metadata: str | None,
    ) -> dict[str, Any]:
        """Insert a new memory entry; return the full row as a dict."""
        entry_id = uuid.uuid4().hex
        created_at = _utcnow()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO memories
                    (id, category, content, importance, source, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (entry_id, category, content, importance, source, created_at, metadata),
            )
            # Keep FTS5 in sync — insert the same rowid explicitly
            row = self._conn.execute(
                "SELECT rowid FROM memories WHERE id = ?", (entry_id,)
            ).fetchone()
            self._conn.execute(
                "INSERT INTO memories_fts(rowid, content, category) VALUES (?, ?, ?)",
                (row["rowid"], content, category),
            )

        return self.get_memory(entry_id, _track_access=False)  # type: ignore[return-value]

    def get_memory(
        self, memory_id: str, *, _track_access: bool = True
    ) -> dict[str, Any] | None:
        """Return a memory entry by ID (and bump access counter), or None."""
        row = self._conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return None

        if _track_access:
            now = _utcnow()
            with self._conn:
                self._conn.execute(
                    """
                    UPDATE memories
                       SET access_count  = access_count + 1,
                           last_accessed = ?
                     WHERE id = ?
                    """,
                    (now, memory_id),
                )
            row = self._conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()

        return _row_to_dict(row)

    def update_memory(self, memory_id: str, **fields: Any) -> None:
        """Update named fields of an existing memory entry (no-op if absent)."""
        if not fields:
            return
        allowed = {
            "category", "content", "importance", "source",
            "last_accessed", "access_count", "metadata",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [memory_id]
        with self._conn:
            self._conn.execute(
                f"UPDATE memories SET {set_clause} WHERE id = ?", values  # noqa: S608
            )

        # Re-sync FTS if text fields changed
        if "content" in updates or "category" in updates:
            row = self._conn.execute(
                "SELECT rowid, content, category FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
            if row:
                with self._conn:
                    self._conn.execute(
                        "DELETE FROM memories_fts WHERE rowid = ?", (row["rowid"],)
                    )
                    self._conn.execute(
                        "INSERT INTO memories_fts(rowid, content, category)"
                        " VALUES (?, ?, ?)",
                        (row["rowid"], row["content"], row["category"]),
                    )

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory entry and its FTS5 row. Return True if found."""
        row = self._conn.execute(
            "SELECT rowid FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return False

        with self._conn:
            self._conn.execute(
                "DELETE FROM memories_fts WHERE rowid = ?", (row["rowid"],)
            )
            self._conn.execute(
                "DELETE FROM memories WHERE id = ?", (memory_id,)
            )
        return True

    def list_memories(
        self, category: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Return a list of memory entries, optionally filtered by category."""
        if category is not None:
            rows = self._conn.execute(
                "SELECT * FROM memories WHERE category = ? LIMIT ?",
                (category, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memories LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # FTS5 search
    # ------------------------------------------------------------------

    def search_memories(
        self,
        query: str,
        category: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Full-text search over memories; ranked by bm25 score."""
        if category is not None:
            sql = """
                SELECT m.*
                  FROM memories m
                  JOIN memories_fts f ON f.rowid = m.rowid
                 WHERE memories_fts MATCH ?
                   AND m.category = ?
                 ORDER BY bm25(memories_fts)
                 LIMIT ?
            """
            rows = self._conn.execute(sql, (query, category, limit)).fetchall()
        else:
            sql = """
                SELECT m.*
                  FROM memories m
                  JOIN memories_fts f ON f.rowid = m.rowid
                 WHERE memories_fts MATCH ?
                 ORDER BY bm25(memories_fts)
                 LIMIT ?
            """
            rows = self._conn.execute(sql, (query, limit)).fetchall()
        return [_row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Raw captures
    # ------------------------------------------------------------------

    def add_raw_capture(
        self,
        event_type: str,
        raw_content: str,
        signal_type: str | None,
        confidence: float,
        session_id: str | None,
    ) -> int:
        """Insert a raw capture; return its integer row ID."""
        timestamp = _utcnow()
        with self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO raw_captures
                    (timestamp, event_type, raw_content, signal_type, confidence, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (timestamp, event_type, raw_content, signal_type, confidence, session_id),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_unprocessed_captures(self) -> list[dict[str, Any]]:
        """Return all raw captures where processed = 0."""
        rows = self._conn.execute(
            "SELECT * FROM raw_captures WHERE processed = 0"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def mark_captures_processed(self, ids: list[int]) -> None:
        """Set processed = 1 for the given row IDs."""
        if not ids:
            return
        placeholders = ", ".join("?" * len(ids))
        with self._conn:
            self._conn.execute(
                f"UPDATE raw_captures SET processed = 1 WHERE id IN ({placeholders})",  # noqa: S608
                ids,
            )

    def count_unprocessed_captures(self) -> int:
        """Return the count of unprocessed raw captures."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM raw_captures WHERE processed = 0"
        ).fetchone()
        return row[0]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return a summary dict of store metrics."""
        total_memories = self._conn.execute(
            "SELECT COUNT(*) FROM memories"
        ).fetchone()[0]

        by_category_rows = self._conn.execute(
            "SELECT category, COUNT(*) AS cnt FROM memories GROUP BY category"
        ).fetchall()
        by_category = {r["category"]: r["cnt"] for r in by_category_rows}

        total_raw = self._conn.execute(
            "SELECT COUNT(*) FROM raw_captures"
        ).fetchone()[0]

        unprocessed = self._conn.execute(
            "SELECT COUNT(*) FROM raw_captures WHERE processed = 0"
        ).fetchone()[0]

        # For :memory: databases page_count is 0; for file DBs it's accurate
        size_row = self._conn.execute(
            "SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()"
        ).fetchone()
        db_size = size_row[0] if size_row else 0

        return {
            "total_memories": total_memories,
            "by_category": by_category,
            "total_raw_captures": total_raw,
            "unprocessed_captures": unprocessed,
            "db_size_bytes": db_size,
        }
