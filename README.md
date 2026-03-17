# amplifier-bundle-project-memory

Persistent project-scoped memory for Amplifier sessions. Hooks automatically
extract memory candidates during work (zero LLM cost), a Scribe agent curates
them into permanent entries at session end, and a Librarian agent injects a
concise briefing at session start — so the agent never begins from zero.

## Install

```bash
# Add the bundle
amplifier bundle add git+https://github.com/michaeljabbour/amplifier-bundle-project-memory@main --name project-memory

# Activate it (standalone)
amplifier bundle use project-memory

# Or include in your existing bundle's YAML:
# includes:
#   - bundle: git+https://github.com/michaeljabbour/amplifier-bundle-project-memory@main
```

Run `amplifier update` at any time to pull the latest version.

## Tool Operations

The `project_memory` tool provides explicit memory management:

| Operation  | Description                                                  |
|------------|--------------------------------------------------------------|
| `remember` | Store a memory explicitly (higher importance, slower decay)  |
| `recall`   | Search memories by keyword (FTS5) or category filter         |
| `forget`   | Delete a specific memory entry by ID                         |
| `list`     | Browse memories with optional category/relevance filters     |
| `maintain` | Prune stale entries, enforce category caps, run decay        |
| `status`   | Show entry counts by category, DB size, last maintenance     |

## Testing the Bundle

A two-session walkthrough to verify everything works end-to-end. Run these
prompts in order inside a project directory.

### Session 1: Build Memory

Open a session in your project directory and try each prompt:

**1. Decision capture**

```
Let's use PostgreSQL for the database. I decided against MySQL because we need
JSONB support for dynamic schemas.
```

Tests: The `hooks-memory-capture` hook detects "decided against" and "let's use"
as decision signals and writes a raw capture.

**2. Blocker capture**

```
We're blocked on the auth integration — waiting on the OAuth credentials from
the identity team.
```

Tests: The hook detects "blocked on" and "waiting on" as blocker signals.

**3. Architecture capture**

```
Create a new file at src/api/routes.py for the REST endpoints
```

Tests: The hook detects file creation as an architecture signal.

**4. Explicit remember**

```
Remember that we chose 15-minute JWT access token expiry as a compromise
between security and UX
```

Tests: The `remember` operation on the `project_memory` tool. Explicit entries
get `source: "explicit"` with a 1.5x importance multiplier, so they decay
slower than auto-captured ones.

**5. Check status**

```
What's in project memory right now?
```

Tests: The `status` and `list` operations. You should see raw captures from
steps 1-3 and the explicit entry from step 4.

### Session 2: Verify Handoff

Close the session from above, then start a **new session** in the same project
directory.

**6. Automatic briefing**

Just start the session — don't say anything project-specific. The Librarian
agent should inject a briefing automatically.

Tests: The `session:start` hook triggers the Librarian agent, which generates a
briefing via `inject_context` with `ephemeral=True` (doesn't accumulate in
conversation history). The agent should "just know" your project context.

**7. Recall**

```
What did we decide about the database?
```

Tests: FTS5 full-text search via the `recall` operation. Results are ranked by
the decay model — recent, high-importance entries score highest.

**8. Pick up where we left off**

```
What's currently blocked?
```

Tests: Category filtering on blocker entries. The auth/OAuth blocker from
Session 1 should surface.

**9. Verify decay**

```
Run maintenance on project memory
```

Tests: The `maintain` operation applies the decay model, enforces per-category
caps, and prunes entries below the relevance threshold.

### What to Watch For

| What to Verify | How to Check |
|----------------|--------------|
| Hooks captured signals | `project_memory status` shows raw capture count > 0 |
| Scribe curated at session end | Session 2 briefing contains curated entries |
| Briefing injected at start | Agent "just knows" project context without being told |
| Explicit vs observed importance | The JWT entry has higher importance than auto-captured ones |
| FTS5 search works | "What did we decide about X?" returns relevant entries |
| Decay model works | Old entries score lower after `maintain` |

### Troubleshooting

| Problem | Fix |
|---------|-----|
| No briefing in Session 2 | Check `.amplifier/project-memory/memory.db` exists in your project dir |
| "Tool not found: project_memory" | Run `amplifier update` to refresh the bundle cache |
| Hooks not capturing | Verify bundle is active: `amplifier bundle list` should show project-memory |

## Architecture

```
session:start
    │
    ▼
Librarian generates briefing (ephemeral — doesn't persist in history)
    │
    ▼
Work ──── hooks-memory-capture monitors tool:post + prompt:complete ──┐
    │     Lightweight heuristics → raw_captures (zero LLM cost)       │
    ▼                                                                 │
(more work...)  ◄─────────────────────────────────────────────────────┘
    │
session:end
    │
    ▼
Scribe processes raw_captures → categorize, score, deduplicate → curated entries
    │
    ▼
Persistent storage (.amplifier/project-memory/memory.db)
    │
    ▼
Next session:start — Librarian reads curated memories → briefing
```

**Two agents, two paths:**

- **Scribe** (`model_role: reasoning`) — Write path. Processes the raw capture
  buffer at session end: triage, categorize, score importance, deduplicate.
- **Librarian** (`model_role: fast`) — Read path. Generates briefings at session
  start, serves recall queries, runs maintenance.

## Configuration

All parameters are optional — the defaults work for most projects.

| Parameter                        | Module                   | Default                                              | Description                                |
|----------------------------------|--------------------------|------------------------------------------------------|--------------------------------------------|
| `token_budget`                   | `hooks-session-briefing` | `1500`                                               | Max tokens for session briefing            |
| `ephemeral`                      | `hooks-session-briefing` | `true`                                               | Whether briefing persists in history       |
| `categories`                     | `hooks-memory-capture`   | All 7 categories                                     | Which categories to capture                |
| `decay_half_life_days`           | `tool-project-memory`    | `14`                                                 | Days until importance halves               |
| `explicit_importance_multiplier` | `tool-project-memory`    | `1.5`                                                | Multiplier for explicit `remember` writes  |
| `max_entries_per_category`       | `tool-project-memory`    | `50`                                                 | Cap per category before pruning            |
| `relevance_threshold`            | `tool-project-memory`    | `0.1`                                                | Minimum relevance score to keep            |
| `db_path`                        | `tool-project-memory`    | `{project_root}/.amplifier/project-memory/memory.db` | Database location                          |

The 7 capture categories: `decision`, `architecture`, `blocker`,
`resolved_blocker`, `dependency`, `pattern`, `lesson_learned`.

## Development

```bash
cd ~/dev/amplifier-bundle-project-memory
pip install -e modules/project-memory-core
pytest tests/ -v
```

Test directories:

| Directory                 | What it tests                                                |
|---------------------------|--------------------------------------------------------------|
| `tests/test_core/`        | Schema, store, decay model, heuristics (unit tests)         |
| `tests/test_tool/`        | Tool module: all 6 operations, mount() contract             |
| `tests/test_hooks/`       | Hook modules: lifecycle handlers, coordinator mock          |
| `tests/test_composition/` | Bundle structure: YAML validity, file references, convergence |

All tests use in-memory SQLite — no file system side-effects, no Amplifier
runtime required.

## License

MIT — see [LICENSE](LICENSE).
