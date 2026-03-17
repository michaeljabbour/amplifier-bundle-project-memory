"""Tests for project_memory_core.store."""

import sqlite3
import time

import pytest

from project_memory_core.store import MemoryStore


@pytest.fixture
def store():
    """In-memory MemoryStore for fast, isolated tests."""
    s = MemoryStore(":memory:")
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_store_in_memory_construction():
    """MemoryStore(':memory:') opens without error and creates schema."""
    s = MemoryStore(":memory:")
    stats = s.get_stats()
    assert stats["total_memories"] == 0
    s.close()


def test_store_context_manager():
    """MemoryStore works as a context manager."""
    with MemoryStore(":memory:") as s:
        assert s.get_stats()["total_memories"] == 0


def test_store_creates_db_file(tmp_path):
    """MemoryStore(path) creates the SQLite file on disk."""
    db_path = tmp_path / "test.db"
    with MemoryStore(str(db_path)) as s:
        s.create_memory("decision", "use SQLite", 0.9, "explicit", None)
    assert db_path.exists()


# ---------------------------------------------------------------------------
# CRUD — create_memory
# ---------------------------------------------------------------------------


def test_create_memory_returns_entry_with_id(store):
    """create_memory returns a dict with a generated UUID id."""
    entry = store.create_memory("decision", "use PostgreSQL", 0.9, "explicit", None)
    assert "id" in entry
    assert len(entry["id"]) == 32  # uuid4().hex is 32 hex chars


def test_create_memory_returns_entry_with_created_at(store):
    """create_memory sets created_at to an ISO timestamp string."""
    entry = store.create_memory("decision", "use Redis", 0.8, "observed", None)
    assert "created_at" in entry
    assert isinstance(entry["created_at"], str)
    assert "T" in entry["created_at"]  # ISO format contains 'T'


def test_create_memory_stores_all_fields(store):
    """create_memory persists category, content, importance, source."""
    entry = store.create_memory(
        "architecture", "added FastAPI dependency", 0.7, "explicit",
        '{"version": "0.100.0"}'
    )
    fetched = store.get_memory(entry["id"])
    assert fetched["category"] == "architecture"
    assert fetched["content"] == "added FastAPI dependency"
    assert fetched["importance"] == pytest.approx(0.7)
    assert fetched["source"] == "explicit"


# ---------------------------------------------------------------------------
# CRUD — get_memory
# ---------------------------------------------------------------------------


def test_get_memory_returns_none_for_missing_id(store):
    """get_memory returns None for an unknown ID."""
    result = store.get_memory("nonexistent-id-abcdef1234567890")
    assert result is None


def test_get_memory_increments_access_count(store):
    """get_memory increments access_count on each call."""
    entry = store.create_memory("decision", "some choice", 0.5, "observed", None)
    eid = entry["id"]

    first = store.get_memory(eid)
    assert first["access_count"] == 1

    second = store.get_memory(eid)
    assert second["access_count"] == 2


def test_get_memory_updates_last_accessed(store):
    """get_memory sets last_accessed to an ISO timestamp."""
    entry = store.create_memory("pattern", "recurring timeout", 0.6, "observed", None)
    fetched = store.get_memory(entry["id"])
    assert fetched["last_accessed"] is not None
    assert "T" in fetched["last_accessed"]


# ---------------------------------------------------------------------------
# CRUD — update_memory
# ---------------------------------------------------------------------------


def test_update_memory_changes_specified_fields(store):
    """update_memory changes only the fields provided."""
    entry = store.create_memory("blocker", "waiting on API key", 0.8, "observed", None)
    eid = entry["id"]

    store.update_memory(eid, importance=0.9, source="explicit")
    updated = store.get_memory(eid)
    assert updated["importance"] == pytest.approx(0.9)
    assert updated["source"] == "explicit"
    # category and content unchanged
    assert updated["category"] == "blocker"
    assert updated["content"] == "waiting on API key"


def test_update_memory_nonexistent_id_is_noop(store):
    """update_memory on a nonexistent ID does not raise."""
    store.update_memory("nonexistent-000000000000000000000", content="x")


# ---------------------------------------------------------------------------
# CRUD — delete_memory
# ---------------------------------------------------------------------------


def test_delete_memory_returns_true_for_existing(store):
    """delete_memory returns True when entry exists."""
    entry = store.create_memory("decision", "drop MySQL", 0.8, "explicit", None)
    assert store.delete_memory(entry["id"]) is True


def test_delete_memory_removes_entry(store):
    """delete_memory removes the entry so get_memory returns None."""
    entry = store.create_memory("decision", "drop MySQL", 0.8, "explicit", None)
    store.delete_memory(entry["id"])
    assert store.get_memory(entry["id"]) is None


def test_delete_memory_returns_false_for_missing(store):
    """delete_memory returns False for nonexistent ID."""
    assert store.delete_memory("does-not-exist-0000000000000000") is False


def test_delete_memory_removes_fts_entry(store):
    """delete_memory removes the FTS5 row so search no longer finds it."""
    entry = store.create_memory(
        "architecture", "authentication OAuth2 tokens", 0.7, "observed", None
    )
    store.delete_memory(entry["id"])
    results = store.search_memories("authentication")
    assert all(r["id"] != entry["id"] for r in results)


# ---------------------------------------------------------------------------
# CRUD — list_memories
# ---------------------------------------------------------------------------


def test_list_memories_returns_all_entries(store):
    """list_memories returns all entries when no filter is applied."""
    store.create_memory("decision", "use Redis", 0.8, "explicit", None)
    store.create_memory("architecture", "monorepo layout", 0.7, "observed", None)
    store.create_memory("blocker", "CI is broken", 0.9, "observed", None)
    entries = store.list_memories()
    assert len(entries) == 3


def test_list_memories_filtered_by_category(store):
    """list_memories returns only entries for the specified category."""
    store.create_memory("decision", "use Redis", 0.8, "explicit", None)
    store.create_memory("decision", "use Postgres", 0.9, "explicit", None)
    store.create_memory("architecture", "monorepo layout", 0.7, "observed", None)
    entries = store.list_memories(category="decision")
    assert len(entries) == 2
    assert all(e["category"] == "decision" for e in entries)


def test_list_memories_respects_limit(store):
    """list_memories respects the limit parameter."""
    for i in range(10):
        store.create_memory("pattern", f"entry {i}", 0.5, "observed", None)
    entries = store.list_memories(limit=3)
    assert len(entries) == 3


def test_list_memories_default_limit_is_50(store):
    """list_memories default limit is 50."""
    for i in range(60):
        store.create_memory("pattern", f"entry {i}", 0.5, "observed", None)
    entries = store.list_memories()
    assert len(entries) == 50


# ---------------------------------------------------------------------------
# FTS5 search
# ---------------------------------------------------------------------------


def test_search_finds_memory_by_keyword(store):
    """search_memories returns entries matching the keyword."""
    store.create_memory(
        "decision", "authentication OAuth tokens", 0.9, "explicit", None
    )
    store.create_memory("pattern", "database connection pool tuning", 0.6, "observed", None)
    store.create_memory("architecture", "REST API versioning strategy", 0.7, "explicit", None)

    results = store.search_memories("authentication")
    assert len(results) >= 1
    assert any("authentication" in r["content"].lower() for r in results)


def test_search_returns_empty_for_no_match(store):
    """search_memories returns an empty list when nothing matches."""
    store.create_memory("decision", "use Redis caching", 0.8, "explicit", None)
    results = store.search_memories("quantum entanglement")
    assert results == []


def test_search_respects_category_filter(store):
    """search_memories filters by category when provided."""
    store.create_memory("decision", "use OAuth tokens for auth", 0.9, "explicit", None)
    store.create_memory("architecture", "auth middleware pipeline", 0.7, "observed", None)

    results = store.search_memories("auth", category="decision")
    assert all(r["category"] == "decision" for r in results)


def test_search_fts_sync_after_create(store):
    """FTS5 index is updated when a memory is created."""
    store.create_memory(
        "decision", "decided to use gRPC for inter-service", 0.85, "explicit", None
    )
    results = store.search_memories("grpc")
    assert len(results) >= 1


def test_search_with_multiple_entries_returns_relevant_first(store):
    """search_memories ranks highly relevant entries first."""
    store.create_memory("pattern", "unrelated content about file system", 0.5, "observed", None)
    store.create_memory("pattern", "another unrelated topic entirely", 0.5, "observed", None)
    store.create_memory("decision", "PostgreSQL chosen for relational data", 0.9, "explicit", None)
    store.create_memory("pattern", "unrelated network timeout pattern", 0.5, "observed", None)
    store.create_memory("architecture", "PostgreSQL schema migrations with alembic", 0.7, "explicit", None)

    results = store.search_memories("PostgreSQL", limit=5)
    assert len(results) >= 2
    contents = [r["content"].lower() for r in results]
    assert all("postgresql" in c for c in contents)


# ---------------------------------------------------------------------------
# Raw captures
# ---------------------------------------------------------------------------


def test_add_raw_capture_returns_id(store):
    """add_raw_capture returns an integer row ID."""
    row_id = store.add_raw_capture(
        "tool:post", "the raw event content", "decision", 0.8, "session-abc"
    )
    assert isinstance(row_id, int)
    assert row_id > 0


def test_get_unprocessed_captures_returns_pending(store):
    """get_unprocessed_captures returns captures where processed=0."""
    store.add_raw_capture("tool:post", "raw content 1", "decision", 0.8, "s1")
    store.add_raw_capture("prompt:complete", "raw content 2", "architecture", 0.7, "s1")
    unprocessed = store.get_unprocessed_captures()
    assert len(unprocessed) == 2


def test_mark_captures_processed(store):
    """mark_captures_processed sets processed=1 for given IDs."""
    id1 = store.add_raw_capture("tool:post", "content a", "blocker", 0.9, "s1")
    id2 = store.add_raw_capture("tool:post", "content b", "pattern", 0.6, "s1")
    store.add_raw_capture("prompt:complete", "content c", "decision", 0.8, "s1")

    store.mark_captures_processed([id1, id2])

    unprocessed = store.get_unprocessed_captures()
    assert len(unprocessed) == 1
    assert unprocessed[0]["raw_content"] == "content c"


def test_count_unprocessed_captures(store):
    """count_unprocessed_captures returns integer count of unprocessed rows."""
    store.add_raw_capture("tool:post", "c1", "decision", 0.8, "s1")
    store.add_raw_capture("tool:post", "c2", "decision", 0.8, "s1")
    assert store.count_unprocessed_captures() == 2

    cid = store.add_raw_capture("tool:post", "c3", "decision", 0.8, "s1")
    store.mark_captures_processed([cid])
    assert store.count_unprocessed_captures() == 2


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def test_get_stats_returns_expected_keys(store):
    """get_stats returns a dict with the required keys."""
    stats = store.get_stats()
    for key in ("total_memories", "by_category", "total_raw_captures",
                "unprocessed_captures", "db_size_bytes"):
        assert key in stats, f"Missing key: {key}"


def test_get_stats_total_memories_count(store):
    """get_stats.total_memories reflects the actual count."""
    store.create_memory("decision", "d1", 0.9, "explicit", None)
    store.create_memory("architecture", "a1", 0.7, "observed", None)
    stats = store.get_stats()
    assert stats["total_memories"] == 2


def test_get_stats_by_category(store):
    """get_stats.by_category breaks down counts by category."""
    store.create_memory("decision", "d1", 0.9, "explicit", None)
    store.create_memory("decision", "d2", 0.8, "explicit", None)
    store.create_memory("blocker", "b1", 0.9, "observed", None)
    stats = store.get_stats()
    assert stats["by_category"]["decision"] == 2
    assert stats["by_category"]["blocker"] == 1


def test_get_stats_raw_captures_count(store):
    """get_stats.total_raw_captures and unprocessed_captures are accurate."""
    store.add_raw_capture("tool:post", "rc1", "decision", 0.8, "s1")
    store.add_raw_capture("tool:post", "rc2", "decision", 0.8, "s1")
    rid = store.add_raw_capture("tool:post", "rc3", "decision", 0.8, "s1")
    store.mark_captures_processed([rid])

    stats = store.get_stats()
    assert stats["total_raw_captures"] == 3
    assert stats["unprocessed_captures"] == 2
