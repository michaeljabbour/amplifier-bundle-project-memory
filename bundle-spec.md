# Bundle Specification: amplifier-bundle-project-memory

## Overview

- **Tier:** Bundle (standalone, composes into other bundles via `includes:`)
- **Purpose:** Persistent project-scoped memory that survives across sessions — automatic capture, curated storage, and session briefings so agents never start from zero.
- **Path:** Create new

## Problem Statement

Sessions are amnesiac. Every new session re-discovers architecture, re-reads files, re-learns decisions. Manual handoff files (SCRATCH.md, CONTEXT-TRANSFER.md) work but require discipline nobody has. Key decisions get buried in 40MB events.jsonl files nobody can read. When a user says "pick up where we left off," the agent has to fake it.

This bundle makes session continuity automatic. Hooks capture candidate memories with zero LLM cost, a Scribe agent curates them at session end, and a briefing is injected at session start. The agent actually knows what happened last time.

## Design Decisions

### Storage: SQLite + FTS5

- One database per project at `${project_root}/.amplifier/project-memory/memory.db`
- Project-scoped, not user-scoped — portable with the repo, doesn't leak across projects
- FTS5 enables fast full-text search over memory entries
- Schema supports categories, importance scores, timestamps, decay metadata

### Capture: Hybrid (Hooks + Agent)

Two layers prevent the firehose problem while keeping capture cost near zero:

| Layer | When | Cost | What It Does |
|-------|------|------|-------------|
| **Hook layer** (always-on) | `tool:post`, `prompt:complete` | Zero LLM | Lightweight heuristics extract candidate entries into `raw_captures` table |
| **Agent layer** (periodic) | `session:end` | LLM cost | Scribe processes raw buffer — categorizes, scores importance, merges duplicates, writes curated entries |

### Session Lifecycle

| Event | Action |
|-------|--------|
| `session:start` | Hook reads curated memory, generates briefing (~1500 token budget), injects via `inject_context` with `ephemeral=True` |
| `tool:post`, `prompt:complete` | Hook extracts candidates into raw capture buffer (zero LLM cost) |
| `session:end` | Hook triggers Scribe agent to process raw capture buffer before session closes |

### Decay Model

- Configurable half-life (default: 14 days)
- Importance multiplier: explicit decisions decay slower than incidental patterns
- Max entry cap per category (prevents unbounded growth)
- Entries below a configurable relevance threshold are pruned during maintenance

### Write Path Economics

| Write Source | Flag | Decay Rate | Purpose |
|-------------|------|-----------|---------|
| Hook → Scribe pipeline | `source: "observed"` | Normal decay | Automatic capture from session activity |
| `tool-project-memory` explicit write | `source: "explicit"` | Slower decay (1.5x importance multiplier) | Intentional user/agent override ("remember this specifically") |

### Memory Categories

`decision`, `architecture`, `blocker`, `resolved_blocker`, `dependency`, `pattern`, `lesson_learned`

---

## File Structure

```
amplifier-bundle-project-memory/
├── bundle.md                              # Thin: includes + brief orientation
├── behaviors/
│   └── project-memory.yaml                # Registers all modules, agents, context, skill
├── agents/
│   ├── scribe.md                          # Write path: raw captures → curated entries
│   └── librarian.md                       # Read path: briefings, maintenance, queries
├── context/
│   ├── instructions.md                    # Root session guidance (≤100 lines, behavior-included)
│   └── memory-schema.md                   # Schema docs (agent @mention only, NOT root)
├── skills/
│   └── project-memory/
│       └── SKILL.md                       # How agents should work with the memory system
├── modules/
│   ├── project-memory-core/               # Shared library: store, schema, decay, heuristics
│   │   ├── pyproject.toml
│   │   └── project_memory_core/
│   │       ├── __init__.py
│   │       ├── store.py                   # MemoryStore class (SQLite + FTS5 operations)
│   │       ├── schema.py                  # DB schema, migrations, table definitions
│   │       ├── decay.py                   # Decay model: half-life, importance multiplier
│   │       └── heuristics.py              # Lightweight extraction patterns (zero LLM)
│   ├── hooks-memory-capture/              # Hook: tool:post, prompt:complete → raw buffer
│   │   ├── pyproject.toml                 # depends on project-memory-core
│   │   └── amplifier_module_hooks_memory_capture/
│   │       └── __init__.py
│   ├── hooks-session-briefing/            # Hook: session:start → inject briefing
│   │   ├── pyproject.toml                 # depends on project-memory-core
│   │   └── amplifier_module_hooks_session_briefing/
│   │       └── __init__.py
│   ├── hooks-session-end-capture/         # Hook: session:end → trigger Scribe
│   │   ├── pyproject.toml                 # depends on project-memory-core
│   │   └── amplifier_module_hooks_session_end_capture/
│   │       └── __init__.py
│   └── tool-project-memory/               # Tool: explicit CRUD for memory store
│       ├── pyproject.toml                 # depends on project-memory-core
│       └── amplifier_module_tool_project_memory/
│           └── __init__.py
├── README.md
└── LICENSE
```

---

## Components

### bundle.md

Thin bundle. Includes foundation and its own behavior. No `@mentions` in the markdown body. Markdown body is an orientation menu listing available capabilities.

```yaml
---
bundle:
  name: project-memory
  version: 0.1.0
  description: |
    Persistent project-scoped memory across sessions.
    Automatic capture via hooks, curated storage, session briefings.

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main  # TODO: pin before release
  - bundle: project-memory:behaviors/project-memory
---
```

### Behaviors

#### `behaviors/project-memory.yaml`

Single behavior — registers all hook modules, the tool module, agents, context, and skill.

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
    source: ./modules/hooks-memory-capture       # TODO: git+https URL before release
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

**Context sink discipline:** Only `instructions.md` is included at root level. `memory-schema.md` is loaded by agents via `@mention` only — it contains detailed schema documentation that only the Scribe and Librarian need.

### Agents

#### `project-memory:scribe`

**Role:** The write path. Processes raw hook captures into curated memory entries.

| Property | Value |
|----------|-------|
| **File** | `agents/scribe.md` |
| **Model role** | `reasoning` |
| **Triggered by** | `hooks-session-end-capture` at `session:end`; can also be invoked manually |
| **Context @mentions** | `@project-memory:context/memory-schema.md` |
| **Tools needed** | `tool-project-memory` (for writing curated entries) |
| **Produces** | Curated memory entries written to `memories` table in SQLite |

**Description (WHY/WHEN/WHAT/HOW):**

> Use when raw capture buffer has unprocessed entries that need curation. Triggered automatically at session end by `hooks-session-end-capture`, or manually when the user wants to force a memory checkpoint.
>
> Reads the `raw_captures` table, categorizes each candidate (decision, architecture, blocker, etc.), scores importance (0.0–1.0), merges duplicates with existing entries, and writes curated entries to the `memories` table. Entries are tagged with `source: "observed"` to distinguish from explicit user writes.
>
> Produces: curated memory entries in the project memory store. Returns a summary of entries added, merged, and discarded.

**Examples:**

```
<example>
Context: Session ending, raw buffer has 12 unprocessed captures
user: (session:end event fires)
assistant: "Triggering project-memory:scribe to process 12 raw captures before session closes."
<commentary>
The hooks-session-end-capture hook invokes the Scribe automatically.
The Scribe processes all raw captures, not just recent ones.
</commentary>
</example>

<example>
Context: User wants to force a memory checkpoint mid-session
user: "Save what we've figured out so far to project memory"
assistant: "I'll delegate to project-memory:scribe to process the current capture buffer."
<commentary>
Manual invocation — the user explicitly wants a checkpoint.
</commentary>
</example>
```

#### `project-memory:librarian`

**Role:** The read path. Generates briefings, serves queries, runs periodic maintenance.

| Property | Value |
|----------|-------|
| **File** | `agents/librarian.md` |
| **Model role** | `fast` |
| **Triggered by** | `hooks-session-briefing` at `session:start`; available for explicit queries |
| **Context @mentions** | `@project-memory:context/memory-schema.md` |
| **Tools needed** | `tool-project-memory` (for reading and maintenance) |
| **Produces** | Session briefing text (injected via `inject_context`); query results; maintenance reports |

**Description (WHY/WHEN/WHAT/HOW):**

> Use when the session needs orientation from project memory. Invoked automatically at session start by `hooks-session-briefing` to generate a concise briefing (~1500 token budget). Also available for explicit queries ("what did we decide about X?") and periodic maintenance (prune stale entries, resolve conflicts, rebalance categories).
>
> Reads the curated `memories` table, applies decay scoring to rank entries by current relevance, and generates a briefing organized by category. For maintenance, applies the decay model to prune entries below the relevance threshold and enforce per-category caps.
>
> Produces: session briefing (ephemeral context injection); query results; maintenance summary.

**Examples:**

```
<example>
Context: New session starting in a project with existing memory
user: (session:start event fires)
assistant: "Generating session briefing from project memory (23 curated entries across 5 categories)."
<commentary>
The hooks-session-briefing hook invokes the Librarian automatically.
The briefing is injected with ephemeral=True so it doesn't persist in conversation history.
</commentary>
</example>

<example>
Context: User wants to query project memory explicitly
user: "What decisions have we made about the authentication system?"
assistant: "I'll delegate to project-memory:librarian to search project memory for authentication decisions."
<commentary>
Explicit query — the Librarian uses FTS5 to search and returns relevant entries.
</commentary>
</example>
```

### Hook Modules

#### `hooks-memory-capture`

| Property | Value |
|----------|-------|
| **Events** | `tool:post`, `prompt:complete` |
| **LLM cost** | Zero |
| **Depends on** | `project-memory-core` |

Lightweight heuristic extraction. On each event, the hook inspects the event payload for signals that indicate a memory-worthy entry:

- **Decision signals:** "decided to", "we'll go with", "the approach is", "chose X over Y"
- **Architecture signals:** file creation patterns, dependency additions, schema changes
- **Blocker signals:** "blocked by", "can't proceed", "waiting on", error patterns
- **Resolution signals:** "fixed", "resolved", "unblocked", "the issue was"
- **Pattern signals:** repeated tool usage patterns, recurring file access patterns

Candidates are written to the `raw_captures` table with: `timestamp`, `event_type`, `raw_content`, `signal_type`, `confidence` (heuristic score 0.0–1.0), `processed` (boolean, default false).

#### `hooks-session-briefing`

| Property | Value |
|----------|-------|
| **Events** | `session:start` |
| **LLM cost** | One Librarian agent invocation per session start |
| **Depends on** | `project-memory-core` |

On session start:
1. Check if memory DB exists for this project (skip if no DB or empty)
2. Invoke the Librarian agent to generate a briefing within the configured token budget
3. Inject the briefing via `inject_context` with `ephemeral=True`

The briefing is ephemeral — it doesn't persist in conversation history and doesn't accumulate across turns.

#### `hooks-session-end-capture`

| Property | Value |
|----------|-------|
| **Events** | `session:end` |
| **LLM cost** | One Scribe agent invocation per session end |
| **Depends on** | `project-memory-core` |

On session end:
1. Check if raw capture buffer has unprocessed entries
2. If yes, invoke the Scribe agent to process the buffer
3. Scribe curates entries before session closes, ensuring the next session's briefing works with already-curated data

### Tool Module

#### `tool-project-memory`

| Property | Value |
|----------|-------|
| **Type** | Tool (standard `mount()` contract) |
| **Depends on** | `project-memory-core` |

CRUD operations for the memory store. All writes via this tool are flagged as `source: "explicit"` to distinguish from hook-driven automatic captures.

**Operations:**

| Operation | Description |
|-----------|-------------|
| `remember` | Create a memory entry (explicit write, 1.5x importance multiplier) |
| `recall` | Query memories by category, keyword (FTS5), or time range |
| `forget` | Delete a specific memory entry by ID |
| `list` | List memories with optional category/relevance filters |
| `maintain` | Trigger maintenance: prune stale entries, enforce caps, run decay |
| `status` | Show memory store stats: entry counts by category, DB size, last maintenance |

**Input schema (primary fields):**

```json
{
  "type": "object",
  "properties": {
    "operation": {
      "type": "string",
      "enum": ["remember", "recall", "forget", "list", "maintain", "status"]
    },
    "content": {
      "type": "string",
      "description": "Memory content (for remember)"
    },
    "category": {
      "type": "string",
      "enum": ["decision", "architecture", "blocker", "resolved_blocker", "dependency", "pattern", "lesson_learned"],
      "description": "Memory category (for remember, recall, list)"
    },
    "query": {
      "type": "string",
      "description": "Search query (for recall, uses FTS5)"
    },
    "id": {
      "type": "string",
      "description": "Memory entry ID (for forget)"
    }
  },
  "required": ["operation"]
}
```

### Shared Library

#### `modules/project-memory-core/`

Not an Amplifier module — a plain Python package that hook and tool modules depend on. Contains the storage layer, schema, decay model, and heuristics that all modules share.

| File | Purpose |
|------|---------|
| `store.py` | `MemoryStore` class — SQLite connection management, CRUD operations, FTS5 queries |
| `schema.py` | DB schema definition, migration support, table creation (`memories`, `raw_captures`) |
| `decay.py` | Decay model — half-life calculation, importance multiplier, relevance scoring |
| `heuristics.py` | Lightweight pattern matching for capture hooks (regex-based, zero LLM) |

**Database schema (key tables):**

```sql
-- Curated memory entries
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    importance REAL DEFAULT 0.5,     -- 0.0–1.0
    source TEXT DEFAULT 'observed',  -- 'observed' | 'explicit'
    created_at TEXT NOT NULL,
    last_accessed TEXT,
    access_count INTEGER DEFAULT 0,
    metadata TEXT                     -- JSON blob for extensibility
);

CREATE VIRTUAL TABLE memories_fts USING fts5(content, category, tokenize='porter');

-- Raw capture buffer (pre-curation)
CREATE TABLE raw_captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,         -- 'tool:post' | 'prompt:complete'
    raw_content TEXT NOT NULL,
    signal_type TEXT,                 -- 'decision' | 'architecture' | 'blocker' | etc.
    confidence REAL DEFAULT 0.5,
    processed INTEGER DEFAULT 0,     -- boolean: has Scribe processed this?
    session_id TEXT
);
```

### Skill

#### `skills/project-memory/SKILL.md`

Discoverable via `load_skill(search="project-memory")`. Teaches agents how to work with the memory system:

- When to capture memories (vs. when to let hooks handle it)
- How to query effectively (FTS5 syntax, category filtering)
- How to structure entries for maximum value (good vs. bad memory content)
- When explicit `remember` is better than relying on automatic capture
- Memory categories and their intended use

### Context Files

#### `context/instructions.md` (root-level, behavior-included)

**Loaded:** Always (via `behaviors/project-memory.yaml` context.include)
**Budget:** ≤100 lines

Contents:
- What the bundle provides (one paragraph)
- How the memory system works (capture → curate → brief lifecycle)
- Available tool operations (brief reference)
- Available agents and when they're triggered
- Note that briefings are ephemeral and automatic

**Who references it:** Every session (root context).

#### `context/memory-schema.md` (agent-level, @mention only)

**Loaded:** On-demand by agents (`@project-memory:context/memory-schema.md`)
**Budget:** No hard limit (not root context)

Contents:
- Full schema documentation for memory entries
- Category definitions with examples of good/bad entries per category
- Importance scoring rubric
- Decay model parameters and configuration
- FTS5 query syntax reference
- Raw capture heuristic patterns

**Who @mentions it:** `scribe.md`, `librarian.md`

---

## Delegation Map

| Concern | Handled By | Notes |
|---------|-----------|-------|
| Memory storage operations | `project-memory-core` (shared library) | All modules depend on this |
| Raw capture extraction | `hooks-memory-capture` (heuristics) | Zero LLM cost, always-on |
| Raw → curated curation | `project-memory:scribe` (agent) | LLM cost at session end |
| Session briefing generation | `project-memory:librarian` (agent) | LLM cost at session start |
| Explicit CRUD | `tool-project-memory` | Direct user/agent access |
| Periodic maintenance | `project-memory:librarian` (agent) | Triggered manually or by policy |
| Memory system guidance | `project-memory` skill | Discoverable via `load_skill` |

**No external agent delegation.** This bundle is self-contained — it does not delegate to foundation agents or other bundle agents at runtime. The Scribe and Librarian are the only agents and they handle all memory concerns.

---

## Ecosystem Position

### What This Bundle Is

- **Standalone bundle** that composes into any bundle via `includes:`
- **Project-scoped** — memory travels with the repo, not with the user
- **Reuses patterns** from letsgo (exponential decay, FTS5) and harness-machine (STATE.yaml orientation) but has zero runtime dependency on either
- **Kernel primitives used:** hook events (`tool:post`, `prompt:complete`, `session:start`, `session:end`), `inject_context` action, standard tool `mount()` contract

### What This Bundle Is NOT

- **Not `amplifier-bundle-memory`** — that bundle (if it exists) provides user-global fact storage. This is project-scoped session memory. Different purpose, no runtime dependency.
- **Not `context-persistent`** — this does not persist raw conversation turns. It captures curated semantic memories.
- **Not an application bundle** — no modes, no recipes, no workflow orchestration. It is infrastructure that other bundles compose.
- **Not provider-specific** — works with any LLM provider for the Scribe/Librarian agent invocations.

### Composition Examples

```yaml
# Any bundle can add project memory
includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: git+https://github.com/user/amplifier-bundle-project-memory@main
  - bundle: my-bundle:behaviors/my-capability

# Or compose just the behavior (without the root bundle)
includes:
  - bundle: git+https://github.com/user/amplifier-bundle-project-memory@main#subdirectory=behaviors/project-memory.yaml
```

---

## Configuration Surface

All configuration via behavior YAML `config:` blocks. No environment variables required.

| Parameter | Module | Default | Description |
|-----------|--------|---------|-------------|
| `token_budget` | `hooks-session-briefing` | `1500` | Max tokens for session briefing |
| `ephemeral` | `hooks-session-briefing` | `true` | Whether briefing persists in conversation history |
| `categories` | `hooks-memory-capture` | All 7 categories | Which categories to capture |
| `decay_half_life_days` | `tool-project-memory` | `14` | Days until importance halves |
| `explicit_importance_multiplier` | `tool-project-memory` | `1.5` | Multiplier for explicit writes |
| `max_entries_per_category` | `tool-project-memory` | `50` | Cap per category |
| `relevance_threshold` | `tool-project-memory` | `0.1` | Minimum relevance score to keep |
| `db_path` | `tool-project-memory` | `{project_root}/.amplifier/project-memory/memory.db` | Database location |

---

## Convergence Expectations

### Level 1: Structural (pass/fail)

| Gate | How to Verify |
|------|--------------|
| `bundle.md` parses as valid YAML | Parse frontmatter between `---` markers |
| Agent references resolve | `agents/scribe.md` and `agents/librarian.md` exist |
| Module source URIs syntactically valid | All `source:` fields are valid paths or `git+https://` URIs |
| No duplicate context loading | `instructions.md` loaded via behavior only; `memory-schema.md` via agent @mention only |
| Shared library importable | `project-memory-core` installs and imports without error |
| Hook modules mount successfully | Each hook registers handlers via `coordinator.on()` |
| Tool module mounts successfully | `tool-project-memory` registers via `coordinator.mount("tools", ...)` |
| SQLite DB creates on first use | `MemoryStore` creates DB and tables when no DB exists |

### Level 2: Philosophical (scored, target ≥ 0.85)

| Criterion (25% each) | Target Score | Key Check |
|----------------------|-------------|-----------|
| **Thin bundle pattern** | 1.0 | bundle.md ≤20 lines frontmatter, no @mentions in body, no redeclaration |
| **Context sink discipline** | 1.0 | 1 root context file (instructions.md ≤100 lines), memory-schema.md at agent level only |
| **Agent description quality** | 1.0 | Both agents have WHY/WHEN/WHAT/HOW + 2 examples with `<commentary>` |
| **Composition hygiene** | 0.75 | Sources use `@main` during dev (flag for pinning); behavior is reusable; no circular includes |

**Expected Level 2 score: 0.94** (composition hygiene docked for unpinned URIs during development).

### Level 3: Functional (scored, target ≥ 0.80)

| Criterion | How to Test |
|-----------|-------------|
| Hook capture works | Fire `tool:post` event with decision-like content → verify `raw_captures` entry created |
| Scribe curation works | Populate raw buffer → invoke Scribe → verify curated entries in `memories` table |
| Session briefing works | Populate memories → simulate session:start → verify `inject_context` called with briefing |
| Tool CRUD works | Call each operation (`remember`, `recall`, `forget`, `list`, `maintain`, `status`) → verify correct behavior |
| FTS5 search works | Create entries → search by keyword → verify relevant results returned |
| Decay model works | Create entries with old timestamps → run maintenance → verify low-relevance entries pruned |
| End-to-end lifecycle | Full session lifecycle: start (briefing) → work (captures) → end (curation) → start again (updated briefing) |
