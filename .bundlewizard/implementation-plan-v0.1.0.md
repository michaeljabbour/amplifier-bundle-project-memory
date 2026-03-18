# amplifier-bundle-project-memory Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Amplifier bundle that provides persistent project-scoped memory across sessions — automatic capture via hooks, curated storage via agents, session briefings at startup, and explicit CRUD via a tool.

**Architecture:** SQLite + FTS5 database per project at `${project_root}/.amplifier/project-memory/memory.db`. Three hook modules handle the session lifecycle (capture during work, briefing at start, curation at end). A shared core library provides storage, decay, and heuristics. Two agents (Scribe for writes, Librarian for reads) handle LLM-cost operations. One tool module exposes explicit CRUD. All wired together by a single behavior YAML and thin bundle.

**Tech Stack:** Python 3.11+, SQLite with FTS5, hatchling build system, pytest for testing, Amplifier module contracts (mount/coordinator pattern).

**Spec:** `bundle-spec.md` in the repo root — all line references below point there.

---

## Dependency Graph

```
Task 1: Scaffold (directory structure, pyproject.toml, empty stubs)
    ↓
Task 2: project-memory-core (schema, store, decay, heuristics + tests)
    ↓ everything below depends on core
├── Task 3: tool-project-memory (6 operations + tests)
├── Task 4: Hook modules (capture, briefing, end-capture + tests)
│       ↓ hooks invoke agents
├── Task 5: Agents (scribe.md, librarian.md, memory-schema.md)
├── Task 6: Context files + skill (instructions.md, SKILL.md)
│       ↓ once all components exist
└── Task 7: Composition (behavior YAML, bundle.md, structural validation)
```

Tasks 3–6 depend on Task 2 but are independent of each other. Task 7 depends on all prior tasks.

---

## Task 1: Scaffold

**Dependencies:** None (first task).

**Goal:** Create the full directory structure, all `pyproject.toml` files with correct entry points, and empty `__init__.py` stubs that satisfy Python's import machinery. After this task, every package is installable (even if it does nothing yet).

### Files to Create

```
amplifier-bundle-project-memory/
├── modules/
│   ├── project-memory-core/
│   │   ├── pyproject.toml
│   │   └── project_memory_core/
│   │       ├── __init__.py
│   │       ├── schema.py          (empty stub)
│   │       ├── store.py           (empty stub)
│   │       ├── decay.py           (empty stub)
│   │       └── heuristics.py      (empty stub)
│   ├── hooks-memory-capture/
│   │   ├── pyproject.toml
│   │   └── amplifier_module_hooks_memory_capture/
│   │       └── __init__.py
│   ├── hooks-session-briefing/
│   │   ├── pyproject.toml
│   │   └── amplifier_module_hooks_session_briefing/
│   │       └── __init__.py
│   ├── hooks-session-end-capture/
│   │   ├── pyproject.toml
│   │   └── amplifier_module_hooks_session_end_capture/
│   │       └── __init__.py
│   └── tool-project-memory/
│       ├── pyproject.toml
│       └── amplifier_module_tool_project_memory/
│           └── __init__.py
├── agents/           (empty dir, populated in Task 5)
├── context/          (empty dir, populated in Task 6)
├── skills/
│   └── project-memory/   (empty dir, populated in Task 6)
├── behaviors/        (empty dir, populated in Task 7)
└── tests/
    ├── conftest.py
    ├── test_core/
    │   ├── __init__.py
    │   ├── test_schema.py    (empty stub)
    │   ├── test_store.py     (empty stub)
    │   ├── test_decay.py     (empty stub)
    │   └── test_heuristics.py (empty stub)
    ├── test_tool/
    │   ├── __init__.py
    │   └── test_tool_project_memory.py (empty stub)
    ├── test_hooks/
    │   ├── __init__.py
    │   └── test_hooks.py     (empty stub)
    └── test_composition/
        ├── __init__.py
        └── test_structural.py (empty stub)
```

### Steps

- [ ] **Step 1: Create directory structure**

Create all directories listed above. Use `mkdir -p` for the nested paths.

- [ ] **Step 2: Create `modules/project-memory-core/pyproject.toml`**

This is a plain Python library — NOT an Amplifier module. No `amplifier.modules` entry point. No dependency on `amplifier-core`.

```toml
[project]
name = "project-memory-core"
version = "0.1.0"
description = "Shared library for project memory: storage, schema, decay model, heuristics"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["project_memory_core"]
```

- [ ] **Step 3: Create `pyproject.toml` for each Amplifier module**

Four modules, all following the same pattern. Each depends on `project-memory-core` and declares an `amplifier.modules` entry point. Key differences per module:

| Module | `name` | Entry point key | Package name |
|--------|--------|-----------------|--------------|
| hooks-memory-capture | `amplifier-module-hooks-memory-capture` | `hooks-memory-capture` | `amplifier_module_hooks_memory_capture` |
| hooks-session-briefing | `amplifier-module-hooks-session-briefing` | `hooks-session-briefing` | `amplifier_module_hooks_session_briefing` |
| hooks-session-end-capture | `amplifier-module-hooks-session-end-capture` | `hooks-session-end-capture` | `amplifier_module_hooks_session_end_capture` |
| tool-project-memory | `amplifier-module-tool-project-memory` | `tool-project-memory` | `amplifier_module_tool_project_memory` |

Template for each:

```toml
[project]
name = "amplifier-module-{MODULE_NAME}"
version = "0.1.0"
description = "{DESCRIPTION}"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = []  # amplifier-core is a peer dep; project-memory-core is a sibling dev dep

[project.entry-points."amplifier.modules"]
{MODULE_NAME} = "amplifier_module_{PACKAGE_SUFFIX}:mount"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["amplifier_module_{PACKAGE_SUFFIX}"]
```

- [ ] **Step 4: Create empty `__init__.py` stubs**

For each module package, create a minimal `__init__.py` with a docstring only. Do NOT create placeholder `mount()` functions yet — those come in Tasks 2–4.

For `project_memory_core/__init__.py`:
```python
"""Project memory core library: storage, schema, decay, and heuristics."""
```

For each Amplifier module `__init__.py`:
```python
"""Amplifier module: {module description}."""
```

For the four core stub files (`schema.py`, `store.py`, `decay.py`, `heuristics.py`):
```python
"""Module docstring describing purpose."""
```

- [ ] **Step 5: Create `tests/conftest.py`**

Shared fixtures for the test suite. The critical one: an in-memory SQLite database factory.

```python
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
```

- [ ] **Step 6: Create empty test stub files**

Each test file gets a docstring and a single skipped placeholder test:

```python
"""Tests for {module}."""

import pytest


@pytest.mark.skip(reason="Stub — implementation pending in Task N")
def test_placeholder():
    pass
```

- [ ] **Step 7: Verify scaffold**

```bash
cd ~/dev/amplifier-bundle-project-memory
# Verify directory structure
find . -type f | sort | head -60
# Verify core library installs
pip install -e modules/project-memory-core
python -c "import project_memory_core; print('OK')"
# Verify test discovery
pytest tests/ --collect-only
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "scaffold: directory structure, pyproject.toml files, empty stubs"
```

### Success Criteria

- All directories exist matching the spec's file structure (spec lines 63–104).
- `pip install -e modules/project-memory-core` succeeds.
- `pytest tests/ --collect-only` discovers test files in all 4 test subdirectories.
- No import errors for any `__init__.py`.

---

## Task 2: Core Library (`project-memory-core`)

**Dependencies:** Task 1 (scaffold must exist).

**Goal:** Implement the four core modules that all other components depend on: `schema.py`, `store.py`, `decay.py`, `heuristics.py`. Include comprehensive pytest tests. This is pure Python + SQLite — no Amplifier dependencies.

### Files to Create/Modify

- Modify: `modules/project-memory-core/project_memory_core/schema.py`
- Modify: `modules/project-memory-core/project_memory_core/store.py`
- Modify: `modules/project-memory-core/project_memory_core/decay.py`
- Modify: `modules/project-memory-core/project_memory_core/heuristics.py`
- Modify: `modules/project-memory-core/project_memory_core/__init__.py` (public exports)
- Modify: `tests/test_core/test_schema.py`
- Modify: `tests/test_core/test_store.py`
- Modify: `tests/test_core/test_decay.py`
- Modify: `tests/test_core/test_heuristics.py`

### Steps

#### schema.py

- [ ] **Step 1: Write `test_schema.py` tests**

Test the following behaviors:
- `init_db(conn)` creates `memories`, `memories_fts`, and `raw_captures` tables.
- Calling `init_db(conn)` twice is idempotent (no errors on second call).
- `memories` table has the exact columns from the spec (id, category, content, importance, source, created_at, last_accessed, access_count, metadata). Reference spec lines 393–404 for exact schema.
- `memories_fts` is an FTS5 virtual table on content + category with porter tokenizer.
- `raw_captures` table has columns from spec lines 409–418.
- Schema version tracking: `get_schema_version(conn)` returns current version number.

- [ ] **Step 2: Implement `schema.py`**

Contents:
- `SCHEMA_VERSION = 1`
- `init_db(conn: sqlite3.Connection) -> None` — runs `CREATE TABLE IF NOT EXISTS` for all three tables using exact SQL from spec lines 392–418. Creates a `schema_meta` table to track version.
- `get_schema_version(conn: sqlite3.Connection) -> int` — reads from `schema_meta`.
- All DDL as module-level constants for testability.

- [ ] **Step 3: Run schema tests**

```bash
pytest tests/test_core/test_schema.py -v
```
Expected: All pass.

#### store.py

- [ ] **Step 4: Write `test_store.py` tests**

Test the following `MemoryStore` behaviors:

*Construction:*
- `MemoryStore(db_path)` creates the DB file and initializes schema if it doesn't exist.
- `MemoryStore(":memory:")` works for testing.

*CRUD on `memories` table:*
- `create_memory(category, content, importance, source, metadata)` → returns entry with generated UUID `id` and `created_at` timestamp.
- `get_memory(id)` → returns the entry or `None`.
- `update_memory(id, **fields)` → updates specified fields only.
- `delete_memory(id)` → removes entry and corresponding FTS5 row. Returns `True` if found, `False` if not.
- `list_memories(category=None, limit=50)` → returns list, optionally filtered by category.

*FTS5 search:*
- `search_memories(query, category=None, limit=20)` → full-text search. Test that a memory with "authentication OAuth" is found by query "auth".
- FTS5 entries are kept in sync: create inserts, delete removes, update re-indexes.

*Raw captures:*
- `add_raw_capture(event_type, raw_content, signal_type, confidence, session_id)` → returns row id.
- `get_unprocessed_captures()` → returns captures where `processed = 0`.
- `mark_captures_processed(ids)` → sets `processed = 1` for given IDs.
- `count_unprocessed_captures()` → returns integer count.

*Access tracking:*
- `get_memory(id)` increments `access_count` and updates `last_accessed`.

*Stats:*
- `get_stats()` → returns dict with `total_memories`, `by_category` counts, `total_raw_captures`, `unprocessed_captures`, `db_size_bytes`.

- [ ] **Step 5: Implement `store.py`**

`MemoryStore` class with:
- `__init__(self, db_path: str | Path)` — opens/creates SQLite connection, calls `schema.init_db()`, enables WAL mode.
- All methods listed in Step 4 above.
- Use `uuid.uuid4().hex` for memory IDs.
- Use `datetime.utcnow().isoformat()` for timestamps.
- FTS5 sync: use triggers or explicit insert/delete in the same transaction.
- `close()` method for cleanup.
- Context manager support (`__enter__`/`__exit__`).

Implementation notes:
- All write operations should be wrapped in transactions.
- FTS5 sync must be explicit (INSERT INTO memories_fts / DELETE FROM memories_fts) since FTS5 content tables don't auto-sync.
- `search_memories` should use `memories_fts MATCH ?` with `bm25()` ranking.

- [ ] **Step 6: Run store tests**

```bash
pytest tests/test_core/test_store.py -v
```
Expected: All pass.

#### decay.py

- [ ] **Step 7: Write `test_decay.py` tests**

Test the following behaviors:
- `compute_relevance(importance, created_at, last_accessed, access_count, source, half_life_days=14)` → returns a float 0.0–1.0.
- A brand-new entry (age=0) has relevance ≈ importance.
- After exactly `half_life_days`, relevance is ≈ importance × 0.5.
- `source="explicit"` entries get `1.5x` importance multiplier before decay (so effective importance = min(importance × 1.5, 1.0)).
- `source="observed"` entries decay at normal rate.
- `last_accessed` resets the decay clock (relevance is based on time since last access, not creation).
- Higher `access_count` provides a small boost (logarithmic, capped).
- `is_below_threshold(relevance, threshold=0.1)` → boolean.
- `rank_memories(memories, half_life_days=14)` → returns list sorted by current relevance descending, with `current_relevance` field added to each entry.

Test with concrete numbers:
- Entry with importance=0.8, age=0 days → relevance ≈ 0.8
- Entry with importance=0.8, age=14 days → relevance ≈ 0.4
- Entry with importance=0.8, age=28 days → relevance ≈ 0.2
- Explicit entry with importance=0.6, age=14 days → relevance ≈ 0.45 (0.6 × 1.5 = 0.9, halved to 0.45)

- [ ] **Step 8: Implement `decay.py`**

The half-life formula: `relevance = effective_importance × (0.5 ^ (age_days / half_life_days))`

Where:
- `effective_importance = min(importance × multiplier, 1.0)`
- `multiplier = 1.5` if `source == "explicit"`, else `1.0`
- `age_days` = days since `last_accessed` (or `created_at` if never accessed)
- Small access bonus: `+ 0.05 × log2(1 + access_count)`, capped so total doesn't exceed 1.0

Functions:
- `compute_relevance(...)` — single entry scoring.
- `is_below_threshold(relevance, threshold=0.1)` — pruning check.
- `rank_memories(memories, half_life_days=14)` — batch ranking.
- Constants: `DEFAULT_HALF_LIFE_DAYS = 14`, `EXPLICIT_IMPORTANCE_MULTIPLIER = 1.5`, `DEFAULT_RELEVANCE_THRESHOLD = 0.1`.

- [ ] **Step 9: Run decay tests**

```bash
pytest tests/test_core/test_decay.py -v
```
Expected: All pass.

#### heuristics.py

- [ ] **Step 10: Write `test_heuristics.py` tests**

Test the following behaviors:
- `extract_signals(text)` → returns list of `Signal(signal_type, matched_text, confidence)` named tuples.
- Decision signals: "decided to use PostgreSQL" → `Signal("decision", ..., confidence≥0.7)`.
- Architecture signals: "created src/auth/middleware.py" → `Signal("architecture", ..., confidence≥0.6)`.
- Blocker signals: "blocked by the API rate limit" → `Signal("blocker", ..., confidence≥0.7)`.
- Resolution signals: "fixed the auth bug" → `Signal("resolved_blocker", ..., confidence≥0.7)`.
- Pattern signals: match repeated patterns — test with multiple tool invocations of same type.
- No false positives: "I decided to have lunch" should NOT produce a high-confidence decision signal (test that mundane sentences produce empty or low-confidence results).
- Multiple signals: a text can contain multiple signals.
- Empty/None input returns empty list.

Reference spec lines 287–292 for the signal patterns.

- [ ] **Step 11: Implement `heuristics.py`**

Regex-based pattern matching. Zero LLM cost — this runs on every `tool:post` and `prompt:complete` event.

```python
from typing import NamedTuple

class Signal(NamedTuple):
    signal_type: str    # "decision" | "architecture" | "blocker" | "resolved_blocker" | "pattern"
    matched_text: str   # the substring that triggered the match
    confidence: float   # 0.0–1.0
```

Pattern groups (from spec lines 287–292):
- **Decision:** `r"(?:decided to|we'll go with|the approach is|chose \w+ over|going with|let's use|settling on)"` → confidence 0.8
- **Architecture:** `r"(?:created? (?:file|directory)|added? (?:dependency|package)|schema (?:change|migration|update))"` → confidence 0.7
- **Blocker:** `r"(?:blocked by|can't proceed|waiting on|unable to|failing because)"` → confidence 0.8
- **Resolution:** `r"(?:fixed|resolved|unblocked|the issue was|root cause was|solved by)"` → confidence 0.8
- **Pattern:** `r"(?:keep (?:running into|seeing)|every time|recurring|pattern of)"` → confidence 0.6

All patterns case-insensitive. Use `re.IGNORECASE`.

Functions:
- `extract_signals(text: str) -> list[Signal]` — main extraction function.
- `SIGNAL_PATTERNS: dict[str, list[tuple[re.Pattern, float]]]` — compiled patterns for each signal type (module-level constant).

- [ ] **Step 12: Run heuristics tests**

```bash
pytest tests/test_core/test_heuristics.py -v
```
Expected: All pass.

#### Wrapup

- [ ] **Step 13: Update `__init__.py` with public exports**

```python
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
```

- [ ] **Step 14: Run full core test suite**

```bash
pytest tests/test_core/ -v --tb=short
```
Expected: All tests pass. Zero failures.

- [ ] **Step 15: Commit**

```bash
git add modules/project-memory-core/ tests/test_core/
git commit -m "feat: implement project-memory-core — schema, store, decay, heuristics"
```

### Success Criteria

- `MemoryStore(":memory:")` creates all tables and performs CRUD without error.
- FTS5 search returns relevant results (porter-stemmed matching works).
- Decay math produces correct relevance scores (verified with concrete numbers).
- Heuristic patterns detect all 5 signal types from spec with appropriate confidence.
- All tests in `tests/test_core/` pass.
- `from project_memory_core import MemoryStore, extract_signals, compute_relevance` works.

### Testing Requirements

- Use in-memory SQLite (`:memory:`) for all store/schema tests — fast, no file cleanup.
- Test FTS5 search accuracy with at least 5 entries, verifying ranking.
- Test decay math with specific age/importance combinations (concrete expected values).
- Test heuristic patterns with both positive matches and negative cases (no false positives).
- Minimum coverage targets: schema 100%, store 90%+, decay 100%, heuristics 90%+.

---

## Task 3: Tool Module (`tool-project-memory`)

**Dependencies:** Task 2 (core library must be implemented).

**Goal:** Implement the Amplifier tool module exposing 6 operations (`remember`, `recall`, `forget`, `list`, `maintain`, `status`) via the standard `mount()` contract. All writes are flagged `source: "explicit"` with 1.5x importance multiplier.

### Files to Create/Modify

- Modify: `modules/tool-project-memory/amplifier_module_tool_project_memory/__init__.py`
- Modify: `tests/test_tool/test_tool_project_memory.py`

### Steps

- [ ] **Step 1: Write tool tests**

In `tests/test_tool/test_tool_project_memory.py`, test:

*mount() contract (per creating-amplifier-modules skill):*
- `mount(coordinator, config)` calls `coordinator.mount("tools", tool, name="project_memory")`.
- Returns a metadata dict with `name`, `version`, `provides` keys (not `None`).
- Tool instance has `name`, `description`, `input_schema`, and callable `execute()`.

*Operation: remember*
- Input: `{"operation": "remember", "content": "We chose PostgreSQL for the database", "category": "decision"}`.
- Creates entry with `source="explicit"`, `importance` reflecting the 1.5x multiplier applied at query time.
- Returns success with the created entry's ID.

*Operation: recall*
- Input: `{"operation": "recall", "query": "database"}`.
- Returns matching entries ranked by relevance.
- With `category` filter: only returns entries in that category.

*Operation: forget*
- Input: `{"operation": "forget", "id": "<valid_id>"}`.
- Deletes the entry and returns success.
- With invalid ID: returns success=False with appropriate message.

*Operation: list*
- Input: `{"operation": "list"}` → returns all entries.
- Input: `{"operation": "list", "category": "decision"}` → filtered.

*Operation: maintain*
- Input: `{"operation": "maintain"}`.
- Runs decay, prunes entries below relevance threshold, enforces per-category caps.
- Returns summary of actions taken.

*Operation: status*
- Input: `{"operation": "status"}`.
- Returns stats: counts by category, DB size, unprocessed captures count.

*Input validation:*
- Missing `operation` → error.
- Invalid operation → error.
- `remember` without `content` → error.
- `forget` without `id` → error.

Use a `MemoryStore(":memory:")` for all tests — inject via config or direct construction.

- [ ] **Step 2: Implement the tool module**

In `__init__.py`, create:

`ProjectMemoryTool` class with:
- `name` property → `"project_memory"`
- `description` property → describes the tool's purpose and available operations (concise, ≤3 sentences).
- `input_schema` property → JSON schema matching spec lines 347–375.
- `execute(input_data)` method → dispatches to `_remember()`, `_recall()`, `_forget()`, `_list()`, `_maintain()`, `_status()` based on `input_data["operation"]`.

`mount(coordinator, config)` function:
- Reads `db_path` from config (default: `{project_root}/.amplifier/project-memory/memory.db`).
- Reads decay/cap config: `decay_half_life_days`, `explicit_importance_multiplier`, `max_entries_per_category`, `relevance_threshold` (spec lines 518–527 for defaults).
- Instantiates `MemoryStore` and `ProjectMemoryTool`.
- Calls `await coordinator.mount("tools", tool, name=tool.name)`.
- Returns metadata dict.

Operation details:
- `_remember`: calls `store.create_memory(category, content, importance=0.5, source="explicit")`. Importance can be optionally provided in input.
- `_recall`: calls `store.search_memories(query, category)`, then `decay.rank_memories()` on results.
- `_forget`: calls `store.delete_memory(id)`.
- `_list`: calls `store.list_memories(category)`, then `decay.rank_memories()`.
- `_maintain`: iterates all memories, computes relevance via `decay.compute_relevance()`, deletes those below threshold, enforces `max_entries_per_category` by keeping top-N by relevance.
- `_status`: calls `store.get_stats()`.

All methods return `ToolResult(success=..., output=...)`.

- [ ] **Step 3: Run tool tests**

```bash
pytest tests/test_tool/ -v
```
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add modules/tool-project-memory/ tests/test_tool/
git commit -m "feat: implement tool-project-memory — 6 operations with explicit write support"
```

### Success Criteria

- `mount()` satisfies the Amplifier module contract (coordinator.mount called, metadata returned).
- All 6 operations work correctly with valid input.
- Input validation rejects malformed requests with clear error messages.
- All writes set `source: "explicit"`.
- `maintain` operation correctly prunes stale entries and enforces caps.
- All tests in `tests/test_tool/` pass.

### Testing Requirements

- Mock the coordinator for `mount()` tests.
- Use real `MemoryStore(":memory:")` for operation tests (integration-style, not mocked).
- Test each operation with both valid and invalid input.
- Test `maintain` with entries of varying ages to verify pruning works.
- Verify `recall` results are ranked by decay-adjusted relevance.

---

## Task 4: Hook Modules

**Dependencies:** Task 2 (core library must be implemented).

**Goal:** Implement all three hook modules that drive the session lifecycle: capture during work, briefing at start, curation at end. Each follows the standard Amplifier hook `mount()` contract.

### Files to Create/Modify

- Modify: `modules/hooks-memory-capture/amplifier_module_hooks_memory_capture/__init__.py`
- Modify: `modules/hooks-session-briefing/amplifier_module_hooks_session_briefing/__init__.py`
- Modify: `modules/hooks-session-end-capture/amplifier_module_hooks_session_end_capture/__init__.py`
- Modify: `tests/test_hooks/test_hooks.py`

### Steps

#### hooks-memory-capture

- [ ] **Step 1: Implement `hooks-memory-capture`**

This hook registers on `tool:post` and `prompt:complete` events. On each event:
1. Extract event payload text content (tool result or prompt completion text).
2. Run `heuristics.extract_signals(text)` on the content.
3. For each signal with confidence above a threshold (default 0.5), write to `raw_captures` table via `store.add_raw_capture()`.
4. No LLM calls. No blocking. Fast path only.

```python
async def mount(coordinator, config=None):
    config = config or {}
    db_path = _resolve_db_path(coordinator)
    store = MemoryStore(db_path)
    min_confidence = config.get("min_confidence", 0.5)
    categories = config.get("categories", DEFAULT_CATEGORIES)

    async def on_tool_post(event):
        """Extract signals from tool results."""
        text = _extract_text(event)
        if not text:
            return
        signals = extract_signals(text)
        session_id = getattr(event, "session_id", None)
        for signal in signals:
            if signal.confidence >= min_confidence and signal.signal_type in _category_map(categories):
                store.add_raw_capture(
                    event_type="tool:post",
                    raw_content=text,
                    signal_type=signal.signal_type,
                    confidence=signal.confidence,
                    session_id=session_id,
                )

    async def on_prompt_complete(event):
        """Extract signals from prompt completions."""
        # Same pattern as on_tool_post but with event_type="prompt:complete"
        ...

    coordinator.on("tool:post", on_tool_post)
    coordinator.on("prompt:complete", on_prompt_complete)

    return {"name": "hooks-memory-capture", "version": "0.1.0", "events": ["tool:post", "prompt:complete"]}
```

Helper `_resolve_db_path(coordinator)` should get the project root from the coordinator context and construct the default path: `{project_root}/.amplifier/project-memory/memory.db`. Create the directory if it doesn't exist.

#### hooks-session-briefing

- [ ] **Step 2: Implement `hooks-session-briefing`**

Registers on `session:start`. On session start:
1. Check if memory DB exists. If not, skip (no briefing for brand-new projects).
2. Check if there are any curated memories. If zero, skip.
3. Invoke the Librarian agent to generate a briefing within the token budget.
4. Inject the briefing via `coordinator.inject_context(text, ephemeral=True)`.

```python
async def mount(coordinator, config=None):
    config = config or {}
    token_budget = config.get("token_budget", 1500)
    ephemeral = config.get("ephemeral", True)

    async def on_session_start(event):
        db_path = _resolve_db_path(coordinator)
        if not Path(db_path).exists():
            return
        store = MemoryStore(db_path)
        stats = store.get_stats()
        if stats["total_memories"] == 0:
            store.close()
            return

        # Delegate to Librarian agent for briefing generation
        briefing = await coordinator.delegate(
            agent="project-memory:librarian",
            task=f"Generate a session briefing within {token_budget} tokens. "
                 f"The project has {stats['total_memories']} memories across categories: "
                 f"{stats['by_category']}.",
        )

        if briefing:
            await coordinator.inject_context(briefing, ephemeral=ephemeral)

        store.close()

    coordinator.on("session:start", on_session_start)

    return {"name": "hooks-session-briefing", "version": "0.1.0", "events": ["session:start"]}
```

**Note on coordinator API:** The exact coordinator methods for `delegate()` and `inject_context()` depend on the Amplifier runtime. Use the coordinator's actual API. The pseudo-code above shows intent — adapt to the real coordinator interface during implementation.

#### hooks-session-end-capture

- [ ] **Step 3: Implement `hooks-session-end-capture`**

Registers on `session:end`. On session end:
1. Check if raw capture buffer has unprocessed entries.
2. If yes, invoke the Scribe agent to process them.
3. The Scribe reads raw captures and writes curated entries.

```python
async def mount(coordinator, config=None):
    async def on_session_end(event):
        db_path = _resolve_db_path(coordinator)
        if not Path(db_path).exists():
            return
        store = MemoryStore(db_path)
        unprocessed = store.count_unprocessed_captures()
        if unprocessed == 0:
            store.close()
            return

        # Delegate to Scribe agent for curation
        await coordinator.delegate(
            agent="project-memory:scribe",
            task=f"Process {unprocessed} unprocessed raw captures into curated memory entries.",
        )

        store.close()

    coordinator.on("session:end", on_session_end)

    return {"name": "hooks-session-end-capture", "version": "0.1.0", "events": ["session:end"]}
```

#### Tests

- [ ] **Step 4: Write hook tests**

In `tests/test_hooks/test_hooks.py`, test:

*hooks-memory-capture:*
- `mount()` registers handlers on `tool:post` and `prompt:complete`.
- Returns metadata dict with `events` list.
- The `on_tool_post` handler: given text with a decision signal, writes to raw captures.
- The `on_tool_post` handler: given text with no signals, writes nothing.
- Confidence threshold is respected (signals below threshold are skipped).

*hooks-session-briefing:*
- `mount()` registers handler on `session:start`.
- When DB doesn't exist, handler returns early (no delegation, no injection).
- When DB exists but is empty, handler returns early.
- When DB has memories, handler invokes delegate and inject_context.

*hooks-session-end-capture:*
- `mount()` registers handler on `session:end`.
- When no unprocessed captures, handler returns early.
- When unprocessed captures exist, handler invokes delegate for scribe.

*All hooks:*
- `mount()` returns metadata dict (not None).

For testing, mock the coordinator with:
- `coordinator.on(event_name, handler)` — capture registered handlers.
- `coordinator.delegate(agent, task)` — mock, verify calls.
- `coordinator.inject_context(text, ephemeral)` — mock, verify calls.

To test the actual handler logic, call the captured handler directly with a mock event.

- [ ] **Step 5: Run hook tests**

```bash
pytest tests/test_hooks/ -v
```
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add modules/hooks-memory-capture/ modules/hooks-session-briefing/ modules/hooks-session-end-capture/ tests/test_hooks/
git commit -m "feat: implement hook modules — capture, briefing, end-capture"
```

### Success Criteria

- Each hook's `mount()` registers the correct event handler(s) via `coordinator.on()`.
- Each hook's `mount()` returns a metadata dict (not None).
- Memory capture hook writes to `raw_captures` when signals are detected.
- Session briefing hook skips when no DB or no memories exist.
- Session end hook skips when no unprocessed captures exist.
- All tests in `tests/test_hooks/` pass.

### Testing Requirements

- Mock the coordinator (cannot test against real Amplifier runtime in unit tests).
- Use real `MemoryStore(":memory:")` for the capture hook to verify actual DB writes.
- Test handler logic directly by calling captured handler functions.
- Test both the "skip" paths (no DB, empty DB, no captures) and the "do work" paths.
- Verify coordinator API calls (delegate, inject_context) are made with correct arguments.

---

## Task 5: Agents (`scribe.md` + `librarian.md`)

**Dependencies:** Task 2 (agents reference core concepts). Independent of Tasks 3–4.

**Goal:** Create the two agent description files and the `memory-schema.md` context file they both @mention. Both agents follow the WHY/WHEN/WHAT/HOW description pattern with 2 examples each.

### Files to Create

- Create: `agents/scribe.md`
- Create: `agents/librarian.md`
- Create: `context/memory-schema.md`

### Steps

- [ ] **Step 1: Create `context/memory-schema.md`**

This file is @mentioned by both agents. It's NOT loaded at root level — only agents reference it. Content (reference spec lines 449–461):

- Full database schema documentation (tables, columns, types, constraints).
- Memory categories with definitions and examples of good vs. bad entries for each:
  - `decision` — "Chose PostgreSQL over MySQL for JSONB support" (good) vs "We talked about databases" (bad).
  - `architecture` — file structure decisions, dependency choices, schema changes.
  - `blocker` — what's blocking progress and why.
  - `resolved_blocker` — how a blocker was resolved.
  - `dependency` — external dependency decisions and version pins.
  - `pattern` — recurring patterns observed across sessions.
  - `lesson_learned` — what went wrong and what to do differently.
- Importance scoring rubric: 0.0–1.0 scale with examples at 0.2, 0.5, 0.8, 1.0.
- Decay model parameters: half-life, explicit multiplier, threshold, per-category caps.
- FTS5 query syntax reference: basic terms, phrases, boolean operators, prefix queries.
- Heuristic signal patterns (what the hooks look for).

Budget: No hard limit (agent-level only), but aim for clarity over length. ~150–200 lines.

- [ ] **Step 2: Create `agents/scribe.md`**

The Scribe is the write path agent. Reference spec lines 187–229 for full details.

Structure:
```markdown
---
meta:
  name: scribe
  description: >
    Write-path agent for project memory. Processes raw hook captures into
    curated memory entries — categorizes, scores importance, merges duplicates.
model_role: reasoning
tools:
  - tool-project-memory
---

# Scribe — Project Memory Write Path

@project-memory:context/memory-schema.md

## WHY
...explain the problem this agent solves...

## WHEN
...when this agent is invoked (session:end, manual checkpoint)...

## WHAT
...what it does: reads raw_captures, categorizes, scores, merges, writes curated entries...

## HOW
...step-by-step process...

## Examples

<example>
...spec example 1 (session end with 12 captures)...
<commentary>
...why this works this way...
</commentary>
</example>

<example>
...spec example 2 (manual mid-session checkpoint)...
<commentary>
...why this works this way...
</commentary>
</example>
```

Key content for the WHAT/HOW sections:
- Read unprocessed entries from `raw_captures` via `tool-project-memory` status/recall.
- For each capture: determine category, score importance (0.0–1.0), check for duplicates/merge candidates in existing memories.
- Write curated entries with `source: "observed"` via `tool-project-memory` remember.
- Mark raw captures as processed.
- Return summary: N added, N merged, N discarded.

- [ ] **Step 3: Create `agents/librarian.md`**

The Librarian is the read path agent. Reference spec lines 231–273.

Structure: Same as Scribe but with `model_role: fast`.

```markdown
---
meta:
  name: librarian
  description: >
    Read-path agent for project memory. Generates session briefings,
    serves memory queries, and runs periodic maintenance.
model_role: fast
tools:
  - tool-project-memory
---
```

Key content:
- **Briefing generation:** Read curated memories, rank by decay-adjusted relevance, generate a concise briefing organized by category within a token budget. Prioritize: active blockers > recent decisions > architecture > patterns.
- **Query handling:** Search memories by keyword or category, return relevant entries with context.
- **Maintenance:** Run the maintain operation — prune stale entries, enforce caps, report what was cleaned.

Examples: spec lines 255–272 (session start briefing + explicit query).

- [ ] **Step 4: Verify agent files**

Check:
- Both files have valid YAML frontmatter (parseable between `---` markers).
- Both @mention `@project-memory:context/memory-schema.md`.
- Both have `meta.name`, `meta.description`, `model_role`, `tools` in frontmatter.
- Both have WHY/WHEN/WHAT/HOW sections.
- Both have exactly 2 `<example>` blocks with `<commentary>`.

```bash
python -c "
import yaml
for agent in ['agents/scribe.md', 'agents/librarian.md']:
    with open(agent) as f:
        content = f.read()
    front = content.split('---')[1]
    data = yaml.safe_load(front)
    assert 'meta' in data, f'{agent}: missing meta'
    assert 'name' in data['meta'], f'{agent}: missing meta.name'
    assert 'model_role' in data, f'{agent}: missing model_role'
    assert 'tools' in data, f'{agent}: missing tools'
    body = content.split('---', 2)[2]
    assert '@project-memory:context/memory-schema.md' in body, f'{agent}: missing @mention'
    for section in ['WHY', 'WHEN', 'WHAT', 'HOW']:
        assert f'## {section}' in body, f'{agent}: missing {section} section'
    assert body.count('<example>') == 2, f'{agent}: need exactly 2 examples'
    assert body.count('<commentary>') == 2, f'{agent}: need exactly 2 commentary blocks'
    print(f'{agent}: OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add agents/ context/memory-schema.md
git commit -m "feat: add scribe and librarian agents with memory-schema context"
```

### Success Criteria

- Both agent files parse as valid markdown with YAML frontmatter.
- Both @mention `memory-schema.md` (not loaded at root level).
- Both have WHY/WHEN/WHAT/HOW + 2 examples with commentary.
- `memory-schema.md` covers all 7 categories with good/bad examples, scoring rubric, decay parameters, FTS5 syntax.
- Scribe uses `model_role: reasoning`, Librarian uses `model_role: fast`.

### Testing Requirements

- YAML frontmatter parses without error.
- Required fields present in frontmatter.
- @mention syntax is correct.
- Section headers present.
- Example count is exactly 2 per agent.
- These checks are structural (no runtime needed) — can be manual or scripted.

---

## Task 6: Context Files + Skill

**Dependencies:** Task 2 (references core concepts). Independent of Tasks 3–5.

**Goal:** Create the root-level context file (`instructions.md`), and the discoverable skill (`SKILL.md`). These provide guidance to agents and sessions about how to work with the memory system.

### Files to Create

- Create: `context/instructions.md`
- Create: `skills/project-memory/SKILL.md`

### Steps

- [ ] **Step 1: Create `context/instructions.md`**

Root session guidance. Loaded via behavior YAML `context.include` — every session sees this. Budget: **≤100 lines**. Reference spec lines 435–447.

Content outline:
1. **What this provides** (1 paragraph): Persistent project-scoped memory. Automatic capture, curated storage, session briefings.
2. **How it works** (lifecycle):
   - Session start → briefing injected automatically (ephemeral).
   - During work → hooks capture candidate memories (zero cost, automatic).
   - Session end → Scribe curates raw captures into permanent entries.
3. **Tool operations** (brief reference table):
   - `remember` — explicitly store a memory (higher importance, slower decay).
   - `recall` — search memories by keyword or category.
   - `forget` — delete a specific memory.
   - `list` — browse all memories.
   - `maintain` — prune stale entries.
   - `status` — show memory store stats.
4. **Agents** (2 lines each):
   - Scribe: write path, triggered at session end or manually.
   - Librarian: read path, triggered at session start or for explicit queries.
5. **Key behaviors:**
   - Briefings are ephemeral — they don't accumulate in conversation history.
   - Use `remember` for important decisions the hooks might miss.
   - The memory is project-scoped — it travels with the repo.

Keep it scannable. No deep schema docs (that's in `memory-schema.md` for agents only).

- [ ] **Step 2: Create `skills/project-memory/SKILL.md`**

Discoverable via `load_skill(search="project-memory")`. Reference spec lines 422–431.

This skill teaches agents (and humans reading skill output) HOW to work effectively with the memory system. It's a usage guide, not an API reference.

Content outline:
1. **Overview:** What project memory is and why it exists.
2. **When to capture explicitly vs. let hooks handle it:**
   - Let hooks capture: routine decisions, file changes, error patterns.
   - Use explicit `remember`: critical architecture decisions, non-obvious context, "this is important" moments, decisions that come from discussion rather than tool output.
3. **How to query effectively:**
   - FTS5 query syntax: simple terms, phrases (`"exact phrase"`), boolean (AND, OR, NOT).
   - Category filtering: use `category` parameter to narrow results.
   - Combine query + category for precision.
4. **How to structure entries for maximum value:**
   - Good: "Chose PostgreSQL over MySQL because we need JSONB support for dynamic schemas"
   - Bad: "We discussed the database"
   - Include the WHY, not just the WHAT.
   - Include alternatives considered when relevant.
5. **Memory categories and intended use:** Brief description of each of the 7 categories with 1-line guidance on when to use each.
6. **Maintenance:** When to run it, what it does, how to interpret results.

Skill format: standard SKILL.md with frontmatter (`name`, `description`, `version`).

- [ ] **Step 3: Verify files**

```bash
# instructions.md: must be ≤100 lines
wc -l context/instructions.md
# SKILL.md: must have frontmatter
python -c "
import yaml
with open('skills/project-memory/SKILL.md') as f:
    content = f.read()
front = content.split('---')[1]
data = yaml.safe_load(front)
assert 'name' in data, 'SKILL.md: missing name'
print('SKILL.md frontmatter OK:', data.get('name'))
"
```

- [ ] **Step 4: Commit**

```bash
git add context/instructions.md skills/
git commit -m "feat: add context instructions and project-memory skill"
```

### Success Criteria

- `context/instructions.md` is ≤100 lines and covers lifecycle, tool ops, and agents.
- `skills/project-memory/SKILL.md` has valid frontmatter and covers capture guidance, query syntax, entry structuring, and categories.
- Neither file duplicates the detailed schema docs from `memory-schema.md`.
- `instructions.md` does NOT @mention any other files (it's root context, not agent context).

### Testing Requirements

- Line count check on `instructions.md` (≤100).
- YAML frontmatter parsing on `SKILL.md`.
- Content review: instructions.md covers all 5 content areas listed above.
- Content review: SKILL.md covers all 6 content areas listed above.

---

## Task 7: Composition + Structural Validation

**Dependencies:** Tasks 1–6 (all components must exist).

**Goal:** Wire everything together with the behavior YAML and bundle.md. Add README.md and LICENSE. Write structural validation tests that verify the bundle is self-consistent and passes Level 1 + Level 2 convergence criteria from the spec.

### Files to Create

- Create: `behaviors/project-memory.yaml`
- Create: `bundle.md`
- Create: `README.md`
- Create: `LICENSE`
- Modify: `tests/test_composition/test_structural.py`

### Steps

- [ ] **Step 1: Create `behaviors/project-memory.yaml`**

Use the exact YAML from spec lines 135–181. This is the behavior that registers everything:

```yaml
bundle:
  name: project-memory-behavior
  version: 0.1.0
  description: |
    Mounts the project memory system: three hook modules for lifecycle capture,
    one tool module for explicit CRUD, two agents (Scribe + Librarian), and
    one skill for memory system guidance.

hooks:
  - module: hooks-memory-capture
    source: ./modules/hooks-memory-capture
    config:
      categories:
        - decision
        - architecture
        - blocker
        - resolved_blocker
        - dependency
        - pattern
        - lesson_learned
  - module: hooks-session-briefing
    source: ./modules/hooks-session-briefing
    config:
      token_budget: 1500
      ephemeral: true
  - module: hooks-session-end-capture
    source: ./modules/hooks-session-end-capture

tools:
  - module: tool-project-memory
    source: ./modules/tool-project-memory
  - module: tool-skills
    source: git+https://github.com/microsoft/amplifier-module-tool-skills@main
    config:
      skills:
        - "@project-memory:skills"

agents:
  include:
    - project-memory:scribe
    - project-memory:librarian

context:
  include:
    - project-memory:context/instructions.md
```

Verify: Only `instructions.md` in context.include. NOT `memory-schema.md` (agent-level only).

- [ ] **Step 2: Create `bundle.md`**

Thin bundle. ≤20 lines YAML frontmatter. No @mentions in the markdown body.

````markdown
---
bundle:
  name: project-memory
  version: 0.1.0
  description: |
    Persistent project-scoped memory across sessions.
    Automatic capture via hooks, curated storage, session briefings.

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: project-memory:behaviors/project-memory
---

# Project Memory

Persistent memory that survives across sessions. The agent remembers decisions,
architecture, blockers, and patterns from previous work.

**Automatic:** Hooks capture memories during work. Scribe curates at session end.
Librarian briefs at session start.

**Explicit:** Use the `project_memory` tool to remember, recall, forget, list,
maintain, or check status.
````

- [ ] **Step 3: Create `README.md`**

Standard project README. Cover:
- What this bundle does (1 paragraph).
- How to include it in another bundle (`includes:` snippet).
- Architecture overview (the session lifecycle diagram from the spec: start->capture->curate->brief).
- Configuration options table (from spec lines 518–527).
- Development setup: `pip install -e modules/project-memory-core && pytest`.

- [ ] **Step 4: Create `LICENSE`**

MIT license. Standard text.

- [ ] **Step 5: Write structural validation tests**

In `tests/test_composition/test_structural.py`, test every Level 1 convergence gate from spec lines 534–544, plus Level 2 checks:

```python
"""Structural validation tests for bundle composition.

Verifies Level 1 (pass/fail) and Level 2 (philosophical) convergence
criteria from the bundle spec.
"""

import yaml
from pathlib import Path

BUNDLE_ROOT = Path(__file__).parent.parent.parent


# --- Level 1: Structural (pass/fail) ---

class TestBundleMdValid:
    def test_frontmatter_parses(self):
        """bundle.md frontmatter parses as valid YAML."""
        content = (BUNDLE_ROOT / "bundle.md").read_text()
        parts = content.split("---")
        assert len(parts) >= 3, "Missing YAML frontmatter delimiters"
        data = yaml.safe_load(parts[1])
        assert "bundle" in data
        assert "includes" in data

    def test_bundle_name(self):
        """bundle.md declares correct bundle name."""
        ...


class TestAgentReferencesResolve:
    def test_scribe_exists(self):
        assert (BUNDLE_ROOT / "agents" / "scribe.md").exists()

    def test_librarian_exists(self):
        assert (BUNDLE_ROOT / "agents" / "librarian.md").exists()

    def test_agents_have_valid_frontmatter(self):
        """Both agents parse and have required fields."""
        ...


class TestModuleSourcesValid:
    def test_behavior_module_sources(self):
        """All source fields in behavior YAML are valid paths or git+https URIs."""
        ...

    def test_local_sources_exist(self):
        """Local source paths (./modules/...) point to existing directories."""
        ...


class TestNoContextDoubleLoad:
    def test_only_instructions_in_behavior_context(self):
        """Only instructions.md in behavior context.include, not memory-schema.md."""
        ...

    def test_memory_schema_only_in_agents(self):
        """memory-schema.md is @mentioned in agents, not in behavior context."""
        ...


# --- Level 2: Philosophical ---

class TestThinBundlePattern:
    def test_frontmatter_line_count(self):
        """bundle.md frontmatter is ≤20 lines."""
        ...

    def test_no_mentions_in_body(self):
        """bundle.md markdown body has no @mentions."""
        ...


class TestContextSinkDiscipline:
    def test_instructions_line_count(self):
        """instructions.md is ≤100 lines."""
        ...

    def test_one_root_context_file(self):
        """Only one file in behavior context.include."""
        ...


class TestAgentDescriptionQuality:
    def test_scribe_sections(self):
        """Scribe has WHY/WHEN/WHAT/HOW + 2 examples with commentary."""
        ...

    def test_librarian_sections(self):
        """Librarian has WHY/WHEN/WHAT/HOW + 2 examples with commentary."""
        ...


class TestCompositionHygiene:
    def test_no_circular_includes(self):
        """Bundle doesn't include itself."""
        ...

    def test_behavior_is_reusable(self):
        """Behavior YAML can be included independently of bundle.md."""
        ...
```

Implement every test method fully — the `...` placeholders above are for plan brevity. Each test should be a concrete assertion, not a stub.

- [ ] **Step 6: Run structural validation**

```bash
pytest tests/test_composition/ -v
```
Expected: All pass.

- [ ] **Step 7: Run the full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: All tests across all 4 test directories pass. Zero failures.

- [ ] **Step 8: Final commit**

```bash
git add behaviors/ bundle.md README.md LICENSE tests/test_composition/
git commit -m "feat: complete bundle composition — behavior YAML, bundle.md, structural validation"
```

### Success Criteria

- `behaviors/project-memory.yaml` registers all 3 hooks, 1 tool, 2 agents, 1 context file, and skill.
- `bundle.md` is a thin bundle with ≤20 lines frontmatter, no @mentions in body.
- All Level 1 convergence gates pass (spec lines 534–544).
- Level 2 convergence score ≥ 0.85 (spec target: 0.94).
- Full test suite (`pytest tests/`) passes with zero failures.
- `README.md` and `LICENSE` exist.

### Testing Requirements

- Every Level 1 gate from the spec has a corresponding test.
- Level 2 criteria (thin bundle, context sink discipline, agent description quality, composition hygiene) each have at least one test.
- Tests use file I/O only — no Amplifier runtime needed.
- Tests validate YAML parsing, file existence, line counts, @mention patterns, section presence.
- The structural tests are the bundle's self-consistency check — they should catch any wiring errors.

---

## Summary

| Task | What | Key Output | Tests |
|------|------|-----------|-------|
| 1 | Scaffold | Directory tree, pyproject.toml, stubs | Install + import check |
| 2 | Core library | schema, store, decay, heuristics | 4 test files, in-memory SQLite |
| 3 | Tool module | 6 operations, mount() contract | Operation + validation tests |
| 4 | Hook modules | 3 hooks for session lifecycle | Mock coordinator tests |
| 5 | Agents | scribe.md, librarian.md, memory-schema.md | Frontmatter + structure checks |
| 6 | Context + skill | instructions.md, SKILL.md | Line count + content checks |
| 7 | Composition | behavior YAML, bundle.md, README, LICENSE | Structural validation suite |

**Total estimated files:** ~35 files created across 7 tasks.

**Critical path:** Task 1 → Task 2 → Tasks 3–6 (parallel) → Task 7.

**Parallelization opportunity:** Tasks 3, 4, 5, and 6 are all independent of each other (they only depend on Task 2). If using subagent-driven-development, these 4 tasks can be dispatched in parallel after Task 2 completes.
