"""Amplifier module: explicit CRUD tool for reading and writing the project memory store."""

import logging
from pathlib import Path
from typing import Any

from amplifier_core import ToolResult
from project_memory_core import (
    MemoryStore,
    compute_relevance,
    rank_memories,
    is_below_threshold,
    DEFAULT_HALF_LIFE_DAYS,
    DEFAULT_RELEVANCE_THRESHOLD,
)

logger = logging.getLogger(__name__)

_VALID_OPERATIONS = frozenset(["remember", "recall", "forget", "list", "maintain", "status"])
_DEFAULT_CATEGORY = "pattern"
_DEFAULT_MAX_ENTRIES_PER_CATEGORY = 50


class ProjectMemoryTool:
    """Explicit CRUD tool for the project memory store.

    Exposes 6 operations: remember, recall, forget, list, maintain, status.
    All writes are flagged source='explicit' to distinguish from hook-driven captures.
    """

    def __init__(
        self,
        store: MemoryStore,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._store = store
        cfg = config or {}
        self._half_life_days: int = int(
            cfg.get("decay_half_life_days", DEFAULT_HALF_LIFE_DAYS)
        )
        self._max_entries_per_category: int = int(
            cfg.get("max_entries_per_category", _DEFAULT_MAX_ENTRIES_PER_CATEGORY)
        )
        self._relevance_threshold: float = float(
            cfg.get("relevance_threshold", DEFAULT_RELEVANCE_THRESHOLD)
        )

    @property
    def name(self) -> str:
        return "project_memory"

    @property
    def description(self) -> str:
        return (
            "Manage the project's persistent memory store with explicit CRUD operations. "
            "Use 'remember' to save important decisions, patterns, blockers, and architectural notes; "
            "'recall' to full-text search by keyword; 'forget' to delete entries by ID; "
            "'list' to browse all or by category; 'maintain' to prune stale entries and enforce caps; "
            "and 'status' to view statistics on store contents."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["remember", "recall", "forget", "list", "maintain", "status"],
                    "description": "Operation to perform",
                },
                "content": {
                    "type": "string",
                    "description": "Memory content (for remember)",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "decision",
                        "architecture",
                        "blocker",
                        "resolved_blocker",
                        "dependency",
                        "pattern",
                        "lesson_learned",
                    ],
                    "description": "Memory category (for remember, recall, list)",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for recall, uses FTS5)",
                },
                "id": {
                    "type": "string",
                    "description": "Memory entry ID (for forget)",
                },
                "importance": {
                    "type": "number",
                    "description": "Importance score 0.0–1.0 (for remember, default: 0.5)",
                },
            },
            "required": ["operation"],
        }

    async def execute(self, input_data: dict[str, Any]) -> ToolResult:
        """Dispatch to the appropriate operation handler."""
        operation = input_data.get("operation")
        if operation is None:
            return ToolResult(
                success=False,
                output="Missing required field: 'operation'",
            )
        if operation not in _VALID_OPERATIONS:
            valid = sorted(_VALID_OPERATIONS)
            return ToolResult(
                success=False,
                output=f"Invalid operation: '{operation}'. Must be one of: {valid}",
            )

        dispatch = {
            "remember": self._remember,
            "recall": self._recall,
            "forget": self._forget,
            "list": self._list,
            "maintain": self._maintain,
            "status": self._status,
        }
        return await dispatch[operation](input_data)

    # ------------------------------------------------------------------
    # Operation handlers
    # ------------------------------------------------------------------

    async def _remember(self, input_data: dict[str, Any]) -> ToolResult:
        """Create a new memory entry with source='explicit'."""
        content = input_data.get("content")
        if not content:
            return ToolResult(
                success=False,
                output="Missing required field: 'content' for operation 'remember'",
            )

        category = input_data.get("category", _DEFAULT_CATEGORY)
        raw_importance = input_data.get("importance", 0.5)
        importance = max(0.0, min(1.0, float(raw_importance)))

        entry = self._store.create_memory(
            category=category,
            content=content,
            importance=importance,
            source="explicit",
            metadata=None,
        )

        return ToolResult(
            success=True,
            output={
                "id": entry["id"],
                "category": entry["category"],
                "content": entry["content"],
                "created_at": entry["created_at"],
            },
        )

    async def _recall(self, input_data: dict[str, Any]) -> ToolResult:
        """Full-text search memories by query, results ranked by decay-adjusted relevance."""
        query = input_data.get("query", "")
        category = input_data.get("category")

        memories = self._store.search_memories(query, category=category)
        ranked = rank_memories(memories, half_life_days=self._half_life_days)

        return ToolResult(success=True, output=ranked)

    async def _forget(self, input_data: dict[str, Any]) -> ToolResult:
        """Delete a memory entry by ID."""
        memory_id = input_data.get("id")
        if not memory_id:
            return ToolResult(
                success=False,
                output="Missing required field: 'id' for operation 'forget'",
            )

        deleted = self._store.delete_memory(memory_id)
        if deleted:
            return ToolResult(success=True, output={"deleted_id": memory_id})

        return ToolResult(
            success=False,
            output=f"Memory entry '{memory_id}' not found",
        )

    async def _list(self, input_data: dict[str, Any]) -> ToolResult:
        """List memory entries (optionally by category), ranked by relevance."""
        category = input_data.get("category")

        memories = self._store.list_memories(category=category)
        ranked = rank_memories(memories, half_life_days=self._half_life_days)

        return ToolResult(success=True, output=ranked)

    async def _maintain(self, _input_data: dict[str, Any]) -> ToolResult:
        """Prune stale entries and enforce per-category caps.

        Two-pass process:
          1. Delete all entries whose current relevance is below the threshold.
          2. For each category, keep only the top-N entries by relevance.
        """
        all_memories = self._store.list_memories(limit=100_000)
        pruned_below_threshold = 0
        pruned_over_cap = 0

        # --- Pass 1: prune below relevance threshold ---
        above_threshold: list[dict[str, Any]] = []
        for memory in all_memories:
            relevance = compute_relevance(
                importance=memory["importance"],
                created_at=memory["created_at"],
                last_accessed=memory.get("last_accessed"),
                access_count=memory.get("access_count", 0),
                source=memory.get("source", "observed"),
                half_life_days=self._half_life_days,
            )
            if is_below_threshold(relevance, self._relevance_threshold):
                self._store.delete_memory(memory["id"])
                pruned_below_threshold += 1
            else:
                above_threshold.append({**memory, "current_relevance": relevance})

        # --- Pass 2: enforce per-category caps ---
        by_category: dict[str, list[dict[str, Any]]] = {}
        for memory in above_threshold:
            by_category.setdefault(memory["category"], []).append(memory)

        for entries in by_category.values():
            if len(entries) > self._max_entries_per_category:
                entries_sorted = sorted(
                    entries, key=lambda e: e["current_relevance"], reverse=True
                )
                for entry in entries_sorted[self._max_entries_per_category:]:
                    self._store.delete_memory(entry["id"])
                    pruned_over_cap += 1

        total_pruned = pruned_below_threshold + pruned_over_cap
        total_kept = len(all_memories) - total_pruned

        return ToolResult(
            success=True,
            output={
                "pruned": total_pruned,
                "pruned_below_threshold": pruned_below_threshold,
                "pruned_over_cap": pruned_over_cap,
                "kept": total_kept,
            },
        )

    async def _status(self, _input_data: dict[str, Any]) -> ToolResult:
        """Return store statistics."""
        stats = self._store.get_stats()
        return ToolResult(success=True, output=stats)


async def mount(
    coordinator: Any,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mount the project_memory tool into the coordinator.

    Reads db_path and decay/cap config from the config dict.
    Creates a MemoryStore and registers a ProjectMemoryTool with the coordinator.
    """
    cfg = config or {}

    db_path = cfg.get("db_path")
    if db_path is None:
        project_root = Path.cwd()
        db_path_obj = project_root / ".amplifier" / "project-memory" / "memory.db"
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)
        db_path = str(db_path_obj)

    store = MemoryStore(db_path)
    tool = ProjectMemoryTool(store, cfg)

    await coordinator.mount("tools", tool, name=tool.name)
    logger.info("tool-project-memory mounted: registered 'project_memory' (db=%s)", db_path)

    return {
        "name": "tool-project-memory",
        "version": "0.1.0",
        "provides": ["project_memory"],
    }
