"""Tests for amplifier_module_tool_project_memory.

Coverage:
  - mount() contract: coordinator.mount called, metadata returned, tool properties present
  - All 6 operations with valid input: remember, recall, forget, list, maintain, status
  - Input validation: missing operation, invalid operation, remember without content, forget without id
  - All writes set source="explicit"
  - Recall returns decay-ranked results with current_relevance keys
  - Maintain prunes entries below relevance threshold and enforces per-category caps
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from project_memory_core import MemoryStore
from amplifier_module_tool_project_memory import mount, ProjectMemoryTool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store():
    s = MemoryStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def tool(store):
    return ProjectMemoryTool(store)


# ---------------------------------------------------------------------------
# mount() contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mount_calls_coordinator_mount():
    """mount() must call coordinator.mount() — the Iron Law."""
    coordinator = MagicMock()
    coordinator.mount = AsyncMock()

    await mount(coordinator, {"db_path": ":memory:"})

    coordinator.mount.assert_called_once()
    call_args = coordinator.mount.call_args
    assert call_args[0][0] == "tools"  # first positional arg is "tools"


@pytest.mark.asyncio
async def test_mount_registers_with_name_kwarg():
    """mount() must pass name='project_memory' as a keyword arg."""
    coordinator = MagicMock()
    coordinator.mount = AsyncMock()

    await mount(coordinator, {"db_path": ":memory:"})

    call_kwargs = coordinator.mount.call_args[1]
    assert call_kwargs.get("name") == "project_memory"


@pytest.mark.asyncio
async def test_mount_returns_metadata_dict():
    """mount() must return a metadata dict with name, version, provides keys."""
    coordinator = MagicMock()
    coordinator.mount = AsyncMock()

    result = await mount(coordinator, {"db_path": ":memory:"})

    assert result is not None
    assert isinstance(result, dict)
    assert "name" in result
    assert "version" in result
    assert "provides" in result


@pytest.mark.asyncio
async def test_mount_metadata_values():
    """mount() metadata must have the correct module name."""
    coordinator = MagicMock()
    coordinator.mount = AsyncMock()

    result = await mount(coordinator, {"db_path": ":memory:"})

    assert result["name"] == "tool-project-memory"
    assert "project_memory" in result["provides"]


@pytest.mark.asyncio
async def test_mount_tool_has_required_properties():
    """The mounted tool must have name, description, input_schema, and callable execute."""
    coordinator = MagicMock()
    coordinator.mount = AsyncMock()

    await mount(coordinator, {"db_path": ":memory:"})

    tool = coordinator.mount.call_args[0][1]
    assert isinstance(tool.name, str) and tool.name == "project_memory"
    assert isinstance(tool.description, str) and len(tool.description) > 0
    assert isinstance(tool.input_schema, dict)
    assert callable(tool.execute)


@pytest.mark.asyncio
async def test_mount_tool_input_schema_structure():
    """Tool input_schema must have required operation field with correct enum."""
    coordinator = MagicMock()
    coordinator.mount = AsyncMock()

    await mount(coordinator, {"db_path": ":memory:"})

    tool = coordinator.mount.call_args[0][1]
    schema = tool.input_schema
    assert schema["type"] == "object"
    assert "operation" in schema["properties"]
    assert "operation" in schema["required"]
    ops = schema["properties"]["operation"]["enum"]
    assert set(ops) == {"remember", "recall", "forget", "list", "maintain", "status"}


# ---------------------------------------------------------------------------
# Operation: remember
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remember_creates_entry_and_returns_id(tool):
    """remember returns success with the created entry's ID."""
    result = await tool.execute({
        "operation": "remember",
        "content": "We chose PostgreSQL for the database",
        "category": "decision",
    })

    assert result.success is True
    assert isinstance(result.output, dict)
    assert "id" in result.output
    assert result.output["id"]  # non-empty


@pytest.mark.asyncio
async def test_remember_sets_source_explicit(tool, store):
    """All remember writes must set source='explicit'."""
    result = await tool.execute({
        "operation": "remember",
        "content": "We chose PostgreSQL for the database",
        "category": "decision",
    })

    assert result.success is True
    entry_id = result.output["id"]
    entry = store.get_memory(entry_id, _track_access=False)
    assert entry is not None
    assert entry["source"] == "explicit"


@pytest.mark.asyncio
async def test_remember_with_custom_importance(tool, store):
    """remember accepts an optional importance value."""
    result = await tool.execute({
        "operation": "remember",
        "content": "Critical architecture decision",
        "category": "architecture",
        "importance": 0.9,
    })

    assert result.success is True
    entry = store.get_memory(result.output["id"], _track_access=False)
    assert abs(entry["importance"] - 0.9) < 0.001


@pytest.mark.asyncio
async def test_remember_without_category_uses_default(tool):
    """remember succeeds even without a category (uses a default)."""
    result = await tool.execute({
        "operation": "remember",
        "content": "A general pattern we noticed",
    })

    assert result.success is True
    assert "id" in result.output


@pytest.mark.asyncio
async def test_remember_persists_content(tool, store):
    """remember persists content and category correctly in the store."""
    result = await tool.execute({
        "operation": "remember",
        "content": "Use Redis for session caching",
        "category": "architecture",
    })

    entry = store.get_memory(result.output["id"], _track_access=False)
    assert entry["content"] == "Use Redis for session caching"
    assert entry["category"] == "architecture"


# ---------------------------------------------------------------------------
# Operation: recall
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recall_returns_matching_entries(tool, store):
    """recall returns entries matching the query."""
    store.create_memory("decision", "We chose PostgreSQL for the database", 0.5, "explicit", None)
    store.create_memory("architecture", "Redis is used for caching", 0.5, "explicit", None)

    result = await tool.execute({"operation": "recall", "query": "database"})

    assert result.success is True
    assert isinstance(result.output, list)
    assert len(result.output) >= 1
    contents = [e["content"] for e in result.output]
    assert any("PostgreSQL" in c for c in contents)


@pytest.mark.asyncio
async def test_recall_with_category_filter(tool, store):
    """recall with category filter returns only entries in that category."""
    store.create_memory("decision", "Use PostgreSQL for the main DB", 0.5, "explicit", None)
    store.create_memory("architecture", "PostgreSQL connection pooling via pgBouncer", 0.5, "explicit", None)

    result = await tool.execute({
        "operation": "recall",
        "query": "PostgreSQL",
        "category": "decision",
    })

    assert result.success is True
    assert isinstance(result.output, list)
    for entry in result.output:
        assert entry["category"] == "decision"


@pytest.mark.asyncio
async def test_recall_results_have_current_relevance(tool, store):
    """recall results include a current_relevance key (decay-ranked)."""
    store.create_memory("decision", "We chose PostgreSQL for the database", 0.5, "explicit", None)

    result = await tool.execute({"operation": "recall", "query": "database"})

    assert result.success is True
    if result.output:
        assert "current_relevance" in result.output[0]


@pytest.mark.asyncio
async def test_recall_results_are_ranked_descending(tool, store):
    """recall results must be sorted by current_relevance descending."""
    store.create_memory("decision", "high importance database choice", 0.9, "explicit", None)
    store.create_memory("decision", "low importance database note", 0.1, "observed", None)

    result = await tool.execute({"operation": "recall", "query": "database"})

    assert result.success is True
    if len(result.output) >= 2:
        scores = [e["current_relevance"] for e in result.output]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Operation: forget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forget_deletes_entry(tool, store):
    """forget removes the entry from the store."""
    entry = store.create_memory("decision", "Temporary decision", 0.5, "explicit", None)
    entry_id = entry["id"]

    result = await tool.execute({"operation": "forget", "id": entry_id})

    assert result.success is True
    assert store.get_memory(entry_id, _track_access=False) is None


@pytest.mark.asyncio
async def test_forget_returns_output_on_success(tool, store):
    """forget returns a non-empty output dict/string on success."""
    entry = store.create_memory("decision", "Some decision", 0.5, "explicit", None)

    result = await tool.execute({"operation": "forget", "id": entry["id"]})

    assert result.success is True
    assert result.output  # has output


@pytest.mark.asyncio
async def test_forget_invalid_id_returns_failure(tool):
    """forget with a nonexistent ID returns success=False with a message."""
    result = await tool.execute({"operation": "forget", "id": "nonexistent-id-xyz-12345"})

    assert result.success is False
    assert result.output  # error message present


# ---------------------------------------------------------------------------
# Operation: list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_returns_all_entries(tool, store):
    """list without filter returns all entries."""
    store.create_memory("decision", "Decision one", 0.5, "explicit", None)
    store.create_memory("architecture", "Architecture one", 0.5, "explicit", None)
    store.create_memory("pattern", "Pattern one", 0.5, "explicit", None)

    result = await tool.execute({"operation": "list"})

    assert result.success is True
    assert isinstance(result.output, list)
    assert len(result.output) == 3


@pytest.mark.asyncio
async def test_list_with_category_filter(tool, store):
    """list with category filter returns only matching entries."""
    store.create_memory("decision", "Decision one", 0.5, "explicit", None)
    store.create_memory("decision", "Decision two", 0.5, "explicit", None)
    store.create_memory("architecture", "Architecture one", 0.5, "explicit", None)

    result = await tool.execute({"operation": "list", "category": "decision"})

    assert result.success is True
    assert isinstance(result.output, list)
    assert len(result.output) == 2
    for entry in result.output:
        assert entry["category"] == "decision"


@pytest.mark.asyncio
async def test_list_results_have_current_relevance(tool, store):
    """list results include current_relevance (decay-ranked)."""
    store.create_memory("decision", "Decision one", 0.5, "explicit", None)

    result = await tool.execute({"operation": "list"})

    assert result.success is True
    if result.output:
        assert "current_relevance" in result.output[0]


@pytest.mark.asyncio
async def test_list_empty_store(tool):
    """list on an empty store returns an empty list."""
    result = await tool.execute({"operation": "list"})

    assert result.success is True
    assert result.output == []


# ---------------------------------------------------------------------------
# Operation: maintain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_maintain_returns_summary(tool):
    """maintain returns a summary dict with pruned and kept counts."""
    result = await tool.execute({"operation": "maintain"})

    assert result.success is True
    assert isinstance(result.output, dict)
    assert "pruned" in result.output
    assert "kept" in result.output


@pytest.mark.asyncio
async def test_maintain_prunes_below_threshold(tool, store):
    """Entries with relevance below threshold are deleted by maintain."""
    # importance=0.0001, source="observed" → no 1.5x multiplier
    # relevance ≈ 0.0001 * decay_factor ≈ 0.0001 << 0.1 threshold
    store.create_memory("decision", "Very low importance entry", 0.0001, "observed", None)
    store.create_memory("decision", "High importance entry", 0.9, "explicit", None)

    result = await tool.execute({"operation": "maintain"})

    assert result.success is True
    remaining = store.list_memories()
    assert len(remaining) == 1
    assert remaining[0]["content"] == "High importance entry"


@pytest.mark.asyncio
async def test_maintain_summary_counts_match_reality(tool, store):
    """maintain summary pruned/kept counts match actual store state."""
    store.create_memory("decision", "Low relevance", 0.0001, "observed", None)
    store.create_memory("decision", "High relevance", 0.9, "explicit", None)

    result = await tool.execute({"operation": "maintain"})

    assert result.success is True
    assert result.output["pruned"] == 1
    assert result.output["kept"] == 1


@pytest.mark.asyncio
async def test_maintain_enforces_per_category_cap(tool, store):
    """maintain removes excess entries when over the per-category cap."""
    small_cap_tool = ProjectMemoryTool(store, {"max_entries_per_category": 3})

    # All with importance high enough to pass the relevance threshold
    for i in range(5):
        store.create_memory(
            "decision",
            f"Decision {i} with sufficient importance",
            importance=0.5 + i * 0.05,  # 0.50 → 0.70
            source="explicit",
            metadata=None,
        )

    result = await small_cap_tool.execute({"operation": "maintain"})

    assert result.success is True
    remaining = store.list_memories(category="decision")
    assert len(remaining) <= 3


@pytest.mark.asyncio
async def test_maintain_keeps_top_by_relevance_when_capping(tool, store):
    """maintain keeps the highest-relevance entries when enforcing caps."""
    small_cap_tool = ProjectMemoryTool(store, {"max_entries_per_category": 2})

    # 4 entries with clearly different importances, all above threshold
    for i, imp in enumerate([0.9, 0.8, 0.3, 0.2]):
        store.create_memory("architecture", f"Architecture note {i}", imp, "explicit", None)

    result = await small_cap_tool.execute({"operation": "maintain"})

    assert result.success is True
    remaining = store.list_memories(category="architecture")
    assert len(remaining) == 2
    # The two kept entries should be the highest-importance ones
    kept_importances = sorted([e["importance"] for e in remaining], reverse=True)
    assert kept_importances[0] >= 0.8
    assert kept_importances[1] >= 0.8


@pytest.mark.asyncio
async def test_maintain_keeps_high_relevance_entries(tool, store):
    """maintain never deletes entries with high relevance."""
    entry = store.create_memory("architecture", "Critical architecture decision", 0.95, "explicit", None)

    result = await tool.execute({"operation": "maintain"})

    assert result.success is True
    assert store.get_memory(entry["id"], _track_access=False) is not None


@pytest.mark.asyncio
async def test_maintain_empty_store(tool):
    """maintain on an empty store returns zero counts."""
    result = await tool.execute({"operation": "maintain"})

    assert result.success is True
    assert result.output["pruned"] == 0
    assert result.output["kept"] == 0


# ---------------------------------------------------------------------------
# Operation: status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_returns_stats_dict(tool, store):
    """status returns a dict with total_memories and by_category."""
    store.create_memory("decision", "Decision one", 0.5, "explicit", None)
    store.create_memory("architecture", "Architecture one", 0.5, "explicit", None)

    result = await tool.execute({"operation": "status"})

    assert result.success is True
    assert isinstance(result.output, dict)
    assert "total_memories" in result.output
    assert "by_category" in result.output
    assert result.output["total_memories"] == 2


@pytest.mark.asyncio
async def test_status_counts_by_category(tool, store):
    """status correctly counts entries per category."""
    store.create_memory("decision", "Decision one", 0.5, "explicit", None)
    store.create_memory("decision", "Decision two", 0.5, "explicit", None)
    store.create_memory("architecture", "Architecture one", 0.5, "explicit", None)

    result = await tool.execute({"operation": "status"})

    assert result.success is True
    assert result.output["by_category"]["decision"] == 2
    assert result.output["by_category"]["architecture"] == 1


@pytest.mark.asyncio
async def test_status_empty_store(tool):
    """status on an empty store returns zero counts."""
    result = await tool.execute({"operation": "status"})

    assert result.success is True
    assert result.output["total_memories"] == 0


@pytest.mark.asyncio
async def test_status_includes_unprocessed_captures(tool):
    """status includes unprocessed_captures count."""
    result = await tool.execute({"operation": "status"})

    assert result.success is True
    assert "unprocessed_captures" in result.output


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_operation_returns_error(tool):
    """Calling execute without 'operation' returns success=False."""
    result = await tool.execute({"content": "some content"})

    assert result.success is False
    assert result.output  # error message present


@pytest.mark.asyncio
async def test_invalid_operation_returns_error(tool):
    """Calling execute with an unknown operation returns success=False."""
    result = await tool.execute({"operation": "nonexistent_op"})

    assert result.success is False
    assert result.output  # error message present


@pytest.mark.asyncio
async def test_remember_without_content_returns_error(tool):
    """remember without 'content' returns success=False."""
    result = await tool.execute({"operation": "remember", "category": "decision"})

    assert result.success is False
    assert result.output  # error message present


@pytest.mark.asyncio
async def test_forget_without_id_returns_error(tool):
    """forget without 'id' returns success=False."""
    result = await tool.execute({"operation": "forget"})

    assert result.success is False
    assert result.output  # error message present


@pytest.mark.asyncio
async def test_error_messages_are_descriptive_strings(tool):
    """All validation error messages are non-empty strings."""
    r1 = await tool.execute({})
    r2 = await tool.execute({"operation": "bad_op"})
    r3 = await tool.execute({"operation": "remember"})
    r4 = await tool.execute({"operation": "forget"})

    for result in [r1, r2, r3, r4]:
        assert result.success is False
        assert isinstance(result.output, str)
        assert len(result.output) > 0
