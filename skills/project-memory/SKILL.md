---
name: project-memory
description: >
  How to work effectively with the project memory system — capture guidance,
  query syntax, entry structuring, categories, and maintenance.
version: 0.1.0
---

# Project Memory Skill

## Overview

Project memory provides persistent, project-scoped storage for decisions, architecture context, blockers, patterns, and lessons learned across sessions. It prevents the "amnesia problem" where each new session re-discovers context that was already established. Memories are automatically captured by hooks, curated by the Scribe agent, and surfaced as briefings by the Librarian agent.

## When to Capture Explicitly vs. Let Hooks Handle It

### Let hooks capture automatically

Hooks fire on `tool:post` and `prompt:complete` events using lightweight heuristics (zero LLM cost). They reliably catch:

- Routine decisions visible in tool output ("created file X", "installed package Y")
- Error patterns and their resolutions
- File changes and dependency additions
- Repeated tool usage patterns

### Use explicit `remember` when

- **Architecture rationale** — The _why_ behind a decision that emerges from discussion, not tool output
- **Rejected alternatives** — "We considered X but chose Y because Z" — hooks only see the choice, not what was rejected
- **Non-obvious context** — Domain constraints, stakeholder requirements, or "gotchas" that came up in conversation
- **Critical decisions** — Anything where you'd say "this is important, don't forget this"
- **Cross-session continuity** — "Next session should start by doing X"

Explicit entries get a 1.5x importance multiplier and decay slower than observed entries.

## How to Query Effectively

### FTS5 query syntax

The `recall` operation uses SQLite FTS5 for full-text search:

| Syntax | Example | Meaning |
|--------|---------|---------|
| Simple terms | `recall query="authentication"` | Entries containing the term |
| Phrases | `recall query="\"API gateway\""` | Exact phrase match |
| AND (implicit) | `recall query="postgres jsonb"` | Both terms must appear |
| OR | `recall query="postgres OR mysql"` | Either term matches |
| NOT | `recall query="database NOT sqlite"` | Exclude entries with second term |
| Prefix | `recall query="auth*"` | Terms starting with "auth" |

### Filtering strategies

- **Category only:** `recall category="decision"` — browse all decisions
- **Query only:** `recall query="authentication"` — search across all categories
- **Combined:** `recall query="authentication" category="decision"` — most precise

Start broad, then narrow. If `recall query="auth"` returns too many results, add a category filter.

## How to Structure Entries for Maximum Value

The difference between useful and useless memories is **specificity and rationale**.

### Good entries

- "Chose PostgreSQL over MySQL because we need JSONB support for dynamic schemas and the team has production Postgres experience"
- "Authentication uses JWT with 15-minute access tokens and 7-day refresh tokens — short access window for security, long refresh for UX"
- "BLOCKED: CI pipeline fails on arm64 runners — the `sharp` package doesn't have prebuilt arm64 binaries. Workaround: use `--platform=linux/amd64` in Docker build"

### Bad entries

- "We discussed the database" — no decision, no rationale
- "Fixed a bug" — which bug? what was the root cause?
- "Authentication works now" — what changed? why?

### Rules of thumb

1. **Include WHY, not just WHAT** — The decision is obvious from code; the rationale is not
2. **Include alternatives considered** — Future sessions need to know what was rejected and why
3. **Be specific** — Names, versions, config values, file paths
4. **One concept per entry** — Don't bundle unrelated decisions into one memory

## Memory Categories

| Category | Use When |
|----------|----------|
| `decision` | A choice was made between alternatives (tech stack, approach, trade-off) |
| `architecture` | Structural decisions about system design, module boundaries, data flow |
| `blocker` | Something is preventing progress — a bug, missing dependency, external wait |
| `resolved_blocker` | A previously-recorded blocker has been resolved (include the resolution) |
| `dependency` | External dependency added, version pinned, or compatibility constraint noted |
| `pattern` | Recurring approach or convention established for the project |
| `lesson_learned` | Something unexpected happened and the takeaway should be preserved |

## Maintenance

### When to run

- **Automatically:** The Librarian runs lightweight maintenance checks during briefing generation
- **Manually:** Run `maintain` when the memory store feels noisy or when `status` shows high entry counts
- **Periodically:** Good practice after major project milestones or long breaks between sessions

### What it does

1. **Decay scoring** — Recalculates relevance scores based on age, importance, and access frequency
2. **Pruning** — Removes entries below the relevance threshold (configurable, default: 0.1)
3. **Cap enforcement** — Enforces per-category entry limits to prevent unbounded growth
4. **Conflict detection** — Flags entries that may contradict each other

### Interpreting results

The maintenance report shows entries pruned, entries retained, and any flagged conflicts. A healthy memory store has entries distributed across categories with relevance scores mostly above 0.3. If most entries are low-relevance, consider whether the capture heuristics are too aggressive for your workflow.
