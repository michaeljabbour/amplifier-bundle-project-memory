"""Project memory core library: storage, schema, decay, and heuristics."""

from project_memory_core.store import MemoryStore
from project_memory_core.schema import init_db, get_schema_version, SCHEMA_VERSION
from project_memory_core.decay import (
    compute_relevance,
    rank_memories,
    is_below_threshold,
    DEFAULT_HALF_LIFE_DAYS,
    EXPLICIT_IMPORTANCE_MULTIPLIER,
    DEFAULT_RELEVANCE_THRESHOLD,
)
from project_memory_core.heuristics import extract_signals, Signal

__all__ = [
    "MemoryStore",
    "init_db",
    "get_schema_version",
    "SCHEMA_VERSION",
    "compute_relevance",
    "rank_memories",
    "is_below_threshold",
    "DEFAULT_HALF_LIFE_DAYS",
    "EXPLICIT_IMPORTANCE_MULTIPLIER",
    "DEFAULT_RELEVANCE_THRESHOLD",
    "extract_signals",
    "Signal",
]
