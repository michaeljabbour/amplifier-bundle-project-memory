# Memory Schema Reference

Complete schema, category definitions, scoring rubric, decay model, and query syntax
for the project memory system.

---

## Database Schema

### `memories` — Curated memory entries

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `id` | TEXT PK | — | UUID for each entry |
| `category` | TEXT NOT NULL | — | One of the 7 memory categories |
| `content` | TEXT NOT NULL | — | The curated memory text |
| `importance` | REAL | `0.5` | Importance score 0.0–1.0 |
| `source` | TEXT | `'observed'` | `'observed'` (hook→scribe) or `'explicit'` (tool write) |
| `created_at` | TEXT NOT NULL | — | ISO 8601 timestamp |
| `last_accessed` | TEXT | NULL | Updated on each read |
| `access_count` | INTEGER | `0` | Incremented on each read |
| `metadata` | TEXT | NULL | JSON blob for extensibility |

### `memories_fts` — Full-text search index

```sql
CREATE VIRTUAL TABLE memories_fts USING fts5(content, category, tokenize='porter');
```

Indexed columns: `content`, `category`. Porter stemming enabled.

### `raw_captures` — Pre-curation buffer

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `id` | INTEGER PK | AUTOINCREMENT | Sequential ID |
| `timestamp` | TEXT NOT NULL | — | ISO 8601 when captured |
| `event_type` | TEXT NOT NULL | — | `'tool:post'` or `'prompt:complete'` |
| `raw_content` | TEXT NOT NULL | — | Raw captured text |
| `signal_type` | TEXT | NULL | Heuristic-detected category hint |
| `confidence` | REAL | `0.5` | Heuristic confidence 0.0–1.0 |
| `processed` | INTEGER | `0` | Boolean: has Scribe processed this? |
| `session_id` | TEXT | NULL | Session that produced this capture |

---

## Memory Categories

Seven categories. Every curated entry must belong to exactly one.

### `decision`
A concrete choice between alternatives with rationale.
- **Good:** "Chose PostgreSQL over MySQL for JSONB support and better concurrent write handling."
- **Bad:** "We talked about databases." (no decision, no rationale)

### `architecture`
Structural choices: file layout, module boundaries, dependency topology, schema design.
- **Good:** "Auth module split into auth-core (no dependencies) and auth-providers (OAuth, SAML) to keep the core testable without provider SDKs."
- **Bad:** "Changed some files around." (no specifics, no reasoning)

### `blocker`
Something actively preventing progress. Include what is blocked and why.
- **Good:** "Blocked: CI pipeline fails on arm64 runners — the ffmpeg binary we vendor is x86-only. Blocks all PRs touching the video module."
- **Bad:** "Something is broken." (no specifics, no scope)

### `resolved_blocker`
How a previously recorded blocker was resolved. Link to the original blocker when possible.
- **Good:** "Resolved arm64 CI blocker: switched to ffmpeg-static npm package which ships multi-arch binaries. CI green on both architectures."
- **Bad:** "Fixed it." (no explanation of what was fixed or how)

### `dependency`
External dependency decisions: additions, removals, version pins, upgrade rationale.
- **Good:** "Pinned pydantic to >=2.4,<3 — v2.4 added the TypeAdapter.validate_strings method we rely on. Cannot upgrade to v3 until we audit all model_validator usage."
- **Bad:** "Added pydantic." (no version, no reasoning)

### `pattern`
Recurring patterns observed across multiple sessions or interactions.
- **Good:** "Pattern: test failures in the payments module are almost always caused by stale Stripe webhook fixtures. First step on any payments test failure should be regenerating fixtures."
- **Bad:** "Tests fail sometimes." (no actionable pattern)

### `lesson_learned`
Something that went wrong and what to do differently. Retrospective insight.
- **Good:** "Lesson: running migrations on the production replica without --dry-run first caused a 20-minute outage. Always dry-run migrations against a replica snapshot before applying to production."
- **Bad:** "That was a mistake." (no specifics, no corrective action)

---

## Importance Scoring Rubric

Scale: **0.0** (noise) to **1.0** (critical). Score reflects how much future sessions need this entry.

| Score | Label | Criteria | Example |
|-------|-------|----------|---------|
| **0.2** | Low | Incidental observation; useful if someone asks, but not worth surfacing proactively | "Tried using `sed -i` on macOS — needed `sed -i ''` with empty string for in-place edit." |
| **0.5** | Medium | Solid context that helps orientation; default for most captured entries | "API rate limiting set to 100 req/min per user, 1000 req/min global. Configured in `config/limits.yaml`." |
| **0.8** | High | Affects active work or multiple components; should appear in briefings | "Authentication switched from session cookies to JWT tokens — all API handlers must validate the Bearer header now. Migration incomplete: 4 of 12 handlers updated." |
| **1.0** | Critical | Active blocker, security issue, or irreversible decision that must not be forgotten | "NEVER run `make reset-db` in production — it drops all tables without confirmation. There is no recovery path. Use `make migrate` instead." |

### Scoring guidelines

- Default to **0.5** when uncertain — the decay model will handle the rest.
- Bump to **0.8+** if the entry affects multiple components or is part of active work.
- Reserve **1.0** for blockers, security-critical items, and "foot-gun" warnings.
- Score **0.2** for incidental tips that are useful but narrow in scope.
- Explicit writes (`source: "explicit"`) get a 1.5x importance multiplier applied by the decay model — a user who explicitly says "remember this" is signaling higher importance.

---

## Decay Model

Relevance decays exponentially so old entries naturally fade unless they remain important.

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `decay_half_life_days` | `14` | Days until effective importance halves |
| `explicit_importance_multiplier` | `1.5` | Multiplier for `source: "explicit"` entries |
| `relevance_threshold` | `0.1` | Entries below this score are pruned during maintenance |
| `max_entries_per_category` | `50` | Hard cap per category; lowest-relevance entries pruned first |

### Relevance formula

```
age_days = (now - created_at) / 86400
decay_factor = 0.5 ^ (age_days / half_life)
effective_importance = importance * source_multiplier
relevance = effective_importance * decay_factor
```

Where `source_multiplier` is `1.5` for `source: "explicit"`, `1.0` for `source: "observed"`.

### Access boost

Entries that are accessed frequently get a small boost: `last_accessed` is updated on each read,
which resets the effective age for decay calculation purposes by blending the creation and
last-access timestamps.

---

## FTS5 Query Syntax

The `memories_fts` table supports SQLite FTS5 query syntax.

| Syntax | Example | Matches |
|--------|---------|---------|
| Simple term | `authentication` | Entries containing "authentication" (stemmed) |
| Phrase | `"rate limiting"` | Exact phrase match |
| AND (implicit) | `postgresql jsonb` | Entries containing both terms |
| OR | `postgresql OR mysql` | Entries containing either term |
| NOT | `database NOT migration` | Entries with "database" but not "migration" |
| Prefix | `auth*` | Entries with terms starting with "auth" |
| Column filter | `category:decision` | Only entries where category matches |
| Combined | `category:blocker auth*` | Blockers with terms starting with "auth" |

### Query tips

- Use prefix queries (`auth*`) when the user's wording may differ from stored content.
- Combine FTS5 with category filters for precise results: recall by category first, then keyword.
- Porter stemming means "running", "runs", "ran" all match the stem "run".

---

## Heuristic Signal Patterns

The `hooks-memory-capture` module uses these lightweight regex patterns (zero LLM cost)
to identify memory candidates from event payloads.

### Decision signals
- "decided to", "we'll go with", "the approach is", "chose X over Y"
- "going with", "let's use", "switching to", "settled on"

### Architecture signals
- File creation/deletion patterns in tool results
- Dependency additions (`pip install`, `npm install`, `cargo add`)
- Schema changes (CREATE TABLE, ALTER TABLE, migration files)
- Module/package restructuring patterns

### Blocker signals
- "blocked by", "can't proceed", "waiting on", "stuck on"
- Repeated error patterns (same error appearing 3+ times)
- "doesn't work", "fails with", "unable to"

### Resolution signals
- "fixed", "resolved", "unblocked", "the issue was"
- "working now", "that solved it", "the fix is"

### Pattern signals
- Repeated tool usage with similar arguments across turns
- Recurring file access patterns (same files opened 3+ times)
- Repeated similar queries or searches

### Confidence scoring

Heuristic confidence is assigned based on signal strength:

| Confidence | Meaning | Action |
|------------|---------|--------|
| 0.8–1.0 | Strong signal (explicit decision language) | Capture with high priority |
| 0.5–0.7 | Moderate signal (contextual patterns) | Capture, let Scribe evaluate |
| 0.3–0.4 | Weak signal (ambiguous patterns) | Capture with low priority |
| < 0.3 | Noise | Discard, do not capture |
