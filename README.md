# amplifier-bundle-project-memory

Persistent project-scoped memory for Amplifier sessions. Hooks automatically
extract memory candidates during work (zero LLM cost), a Scribe agent curates
them into permanent entries at session end, and a Librarian agent injects a
concise briefing at session start — so the agent never begins from zero.

---

## How to Include

Add to your bundle's `includes:` list:

```yaml
includes:
  - bundle: git+https://github.com/microsoft/amplifier-bundle-project-memory@main
```

That's it. The behavior YAML wires all hooks, tools, agents, and context
automatically.

---

## Session Lifecycle

```
session:start
    │
    ▼
[Librarian] Generate briefing from curated memories
    │  (ephemeral — doesn't accumulate in history)
    ▼
Work begins ─────────────────────────────────────────────────────────┐
    │                                                                 │
    ▼                                                                 │
[hooks-memory-capture] Monitor tool:post + prompt:complete events    │
    │  Lightweight heuristics extract candidates → raw_captures      │
    │  Zero LLM cost during capture                                   │
    ▼                                                                 │
(more work...)  ◄────────────────────────────────────────────────────┘
    │
session:end
    │
    ▼
[Scribe] Process raw_captures buffer
    │  Categorize, score importance, deduplicate
    │  Write curated entries to memories table
    ▼
Persistent storage (.amplifier/project-memory/memory.db)
    │
    ▼
(next session:start — Librarian reads updated memories)
```

---

## Tool Operations

Use the `project_memory` tool for explicit memory management:

| Operation  | Description                                                  |
|------------|--------------------------------------------------------------|
| `remember` | Store a memory explicitly (higher importance, slower decay)  |
| `recall`   | Search memories by keyword (FTS5) or category filter         |
| `forget`   | Delete a specific memory entry by ID                         |
| `list`     | Browse memories with optional category/relevance filters     |
| `maintain` | Prune stale entries, enforce category caps, run decay        |
| `status`   | Show entry counts by category, DB size, last maintenance     |

---

## Configuration

All parameters are optional — the defaults work for most projects.

| Parameter                        | Module                    | Default                                               | Description                                       |
|----------------------------------|---------------------------|-------------------------------------------------------|---------------------------------------------------|
| `token_budget`                   | `hooks-session-briefing`  | `1500`                                                | Max tokens for session briefing                   |
| `ephemeral`                      | `hooks-session-briefing`  | `true`                                                | Whether briefing persists in conversation history |
| `categories`                     | `hooks-memory-capture`    | All 7 categories                                      | Which categories to capture                       |
| `decay_half_life_days`           | `tool-project-memory`     | `14`                                                  | Days until importance halves                      |
| `explicit_importance_multiplier` | `tool-project-memory`     | `1.5`                                                 | Multiplier for explicit writes                    |
| `max_entries_per_category`       | `tool-project-memory`     | `50`                                                  | Cap per category                                  |
| `relevance_threshold`            | `tool-project-memory`     | `0.1`                                                 | Minimum relevance score to keep                   |
| `db_path`                        | `tool-project-memory`     | `{project_root}/.amplifier/project-memory/memory.db`  | Database location                                 |

---

## Architecture

```
amplifier-bundle-project-memory/
├── bundle.md                          # Thin bundle: declares includes only
├── behaviors/
│   └── project-memory.yaml            # Wires all modules, agents, context
├── modules/
│   ├── project-memory-core/           # Shared library: schema, store, decay, heuristics
│   ├── hooks-memory-capture/          # Hook: tool:post + prompt:complete → raw_captures
│   ├── hooks-session-briefing/        # Hook: session:start → Librarian briefing
│   ├── hooks-session-end-capture/     # Hook: session:end → Scribe curation
│   └── tool-project-memory/           # Tool: remember/recall/forget/list/maintain/status
├── agents/
│   ├── scribe.md                      # Write-path agent: raw captures → curated entries
│   └── librarian.md                   # Read-path agent: briefings, queries, maintenance
├── context/
│   ├── instructions.md                # Root context (≤100 lines): how to use the system
│   └── memory-schema.md               # Agent-level context: schema, categories, rubric
└── skills/
    └── project-memory/
        └── SKILL.md                   # Skill: guidance for the memory system
```

**Two agents, two paths:**

- **Scribe** (`model_role: reasoning`) — Write path. Processes the raw capture
  buffer at session end: triage, categorize, score importance, deduplicate, write
  curated entries. Invoked automatically by `hooks-session-end-capture`, or
  manually for mid-session checkpoints.

- **Librarian** (`model_role: fast`) — Read path. Generates briefings, serves
  memory queries, runs maintenance. Invoked automatically by
  `hooks-session-briefing` at session start.

**Context discipline:**

- `instructions.md` is loaded at the behavior level (≤100 lines, always available).
- `memory-schema.md` is loaded at the agent level only (via `@mention` in scribe.md
  and librarian.md) — detailed reference material the main session context doesn't need.

---

## Development Setup

```bash
# Clone and install the core library in editable mode
git clone https://github.com/microsoft/amplifier-bundle-project-memory
cd amplifier-bundle-project-memory
pip install -e modules/project-memory-core

# Run the full test suite
pytest tests/ -v

# Run only structural / composition tests
pytest tests/test_composition/ -v

# Run only core library tests
pytest tests/test_core/ -v
```

**Test layout:**

| Directory                 | What it tests                                                          |
|---------------------------|------------------------------------------------------------------------|
| `tests/test_core/`        | Schema, store, decay model, heuristics (unit tests)                    |
| `tests/test_tool/`        | Tool module: all 6 operations, mount() contract                        |
| `tests/test_hooks/`       | Hook modules: lifecycle handlers, coordinator mock                     |
| `tests/test_composition/` | Bundle structure: YAML validity, file references, Level 1+2 convergence |

All tests use in-memory SQLite — no file system side-effects, no Amplifier
runtime required.

---

## License

MIT — see [LICENSE](LICENSE).
