# Project Memory

This bundle provides persistent project-scoped memory that survives across sessions. Hooks automatically capture candidate memories during work, a Scribe agent curates them into permanent entries at session end, and a briefing is injected at session start — so you never start from zero.

## How It Works

The memory system follows a three-phase lifecycle:

1. **Session start** — A briefing summarizing relevant memories is injected automatically. The briefing is ephemeral: it provides orientation without accumulating in conversation history.

2. **During work** — Hooks on `tool:post` and `prompt:complete` events extract candidate memories using lightweight heuristics (zero LLM cost). Candidates are buffered, not yet curated.

3. **Session end** — The Scribe agent processes the raw capture buffer: categorizing, scoring importance, merging duplicates, and writing curated entries to permanent storage.

## Tool Operations

Use the `project-memory` tool for explicit memory operations:

| Operation  | Description                                                 |
|------------|-------------------------------------------------------------|
| `remember` | Store a memory explicitly (higher importance, slower decay)  |
| `recall`   | Search memories by keyword (FTS5) or category               |
| `forget`   | Delete a specific memory entry by ID                        |
| `list`     | Browse memories with optional category/relevance filters    |
| `maintain` | Prune stale entries, enforce caps, run decay                |
| `status`   | Show entry counts by category, DB size, last maintenance    |

## Agents

**Scribe** — The write path. Processes raw hook captures into curated memory entries.
Triggered automatically at session end, or manually for mid-session checkpoints.

**Librarian** — The read path. Generates session briefings, serves explicit queries, runs maintenance.
Triggered automatically at session start, or on-demand for memory queries.

## Key Behaviors

- **Briefings are ephemeral** — They orient you at session start but don't persist in conversation history. Each session gets a fresh briefing based on current relevance.

- **Use `remember` for what hooks miss** — Hooks capture decisions and patterns from tool output, but important context from discussion (architecture rationale, rejected alternatives) should be stored explicitly.

- **Memory is project-scoped** — The memory store lives in the project directory and travels with the repo. It doesn't leak across projects or users.

- **Categories structure memory** — Entries are categorized as: `decision`, `architecture`, `blocker`, `resolved_blocker`, `dependency`, `pattern`, or `lesson_learned`.

- **Decay keeps memory fresh** — Entries lose relevance over time (configurable half-life). Explicit entries decay slower than observed ones. Maintenance prunes entries below the relevance threshold.
