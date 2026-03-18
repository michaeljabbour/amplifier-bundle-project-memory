# Bundle Spec: project-memory v0.1.0 → v0.1.1 (Upgrade)

- **Path:** Improve existing
- **Tier:** Bundle (unchanged)
- **Scope:** Surgical audit fixes — no architectural changes
- **Baseline:** 0.97 level score, 222/223 tests passing, main branch clean
- **Target:** All 5 audit findings resolved, 223/223 tests passing

---

## Task 1 — Migrate provenance key (CRITICAL)

**Problem:** The frontmatter uses `bundle.bundlewizard` as the provenance key. The correct schema key is `bundle.generated_by`.

**Current** (bundle.md lines 8–14):
```yaml
  bundlewizard:
    packaged_at: 2026-03-18T18:57:00Z
    level_score: 0.97
    critic_verdict: PASS
    tests_passed: 223
    tests_failed: 0
    commits: 8
```

**Target:**
```yaml
  generated_by:
    tool: bundlewizard
    packaged_at: 2026-03-18T18:57:00Z
    level_score: 0.97
    critic_verdict: PASS
    tests_passed: 223
    tests_failed: 0
    commits: 8
```

**Files:** `bundle.md`

**Rules:**
- Rename key `bundlewizard` → `generated_by`
- Add `tool: bundlewizard` as the first child key
- All other child values stay identical
- Do NOT touch the `upgrades` array yet — Task 3 handles that

---

## Task 2 — Add schema_version to frontmatter

**Problem:** bundle.md frontmatter does not declare which bundle spec schema it conforms to.

**Change:** Add `schema_version: 1` as the first key under `bundle:`, before `name:`.

**Target** (bundle.md lines 2–4):
```yaml
bundle:
  schema_version: 1
  name: project-memory
  version: 0.1.0
```

**Files:** `bundle.md`

**Rules:**
- Insert as first child of `bundle:`
- Value is integer `1`, not string

---

## Task 3 — Slim frontmatter to ≤20 non-empty lines

**Problem:** The `upgrades` array in bundle.md frontmatter pushes the non-empty line count to 23 (after Tasks 1–2, it will be 24 due to the added `schema_version` and `tool` lines). The bundle's own test (`test_frontmatter_line_count` in `tests/test_composition/test_structural.py`) enforces a ≤20 limit. This is the 1 failing test out of 223.

**Strategy:**
1. Remove the entire `upgrades:` array from bundle.md frontmatter
2. Create `CHANGELOG.md` in the repo root to hold upgrade history
3. Compact the `generated_by` block by removing `tests_failed: 0` (zero-value, redundant with `tests_passed: 223`)

**Target frontmatter** (complete, after Tasks 1–3):
```yaml
---
bundle:
  schema_version: 1
  name: project-memory
  version: 0.1.0
  description: |
    Persistent project-scoped memory across sessions.
    Automatic capture via hooks, curated storage, session briefings.
  generated_by:
    tool: bundlewizard
    packaged_at: 2026-03-18T18:57:00Z
    level_score: 0.97
    critic_verdict: PASS
    tests_passed: 223
    commits: 8

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: project-memory:behaviors/project-memory
---
```

Non-empty line count: **18** (within ≤20 limit).

**CHANGELOG.md** (new file, repo root):
```markdown
# Changelog

## v0.1.1 — 2026-03-18

- Migrate provenance key `bundlewizard` → `generated_by`
- Add `schema_version: 1` to bundle.md frontmatter
- Slim frontmatter to ≤20 non-empty lines
- Add heuristic patterns for `dependency` and `lesson_learned` categories
- Move development artifacts to `.bundlewizard/`

## v0.1.0 — 2026-03-18

- Extract `_resolve_db_path` into project-memory-core/paths.py (DRY)
- Declare project-memory-core as dependency in all module pyproject.toml
- Replace relative source URIs with git+https in behavior YAML
- Add amplifier_core test shim in conftest.py for runtime-free testing
```

**Files:** `bundle.md`, `CHANGELOG.md` (new)

---

## Task 4 — Add heuristic patterns for `dependency` and `lesson_learned`

**Problem:** The behavior YAML configures 7 categories:
`decision`, `architecture`, `blocker`, `resolved_blocker`, `dependency`, `pattern`, `lesson_learned`

But `SIGNAL_PATTERNS` in heuristics.py only has regex groups for 5. The `dependency` and `lesson_learned` categories have no extraction patterns, so `extract_signals()` can never emit them. The hooks-memory-capture module passes them through via config, but no signals ever match — these categories are dead for heuristic capture.

**Change:** Add two new entries to `SIGNAL_PATTERNS` in heuristics.py:

```python
"dependency": [
    (
        re.compile(
            r"(?:added? (?:package|library|module)\b"
            r"|installed? \w+"
            r"|pinned? (?:to |at )?v?\d"
            r"|upgraded? \w+ (?:to|from)"
            r"|requires? \w+ [><=!]"
            r"|version (?:bump|constraint|pin))",
            re.IGNORECASE,
        ),
        0.7,
    ),
],
"lesson_learned": [
    (
        re.compile(
            r"(?:lesson learned"
            r"|in hindsight"
            r"|next time (?:we |I )should"
            r"|should have (?:done|used|started)"
            r"|mistake was"
            r"|the takeaway is"
            r"|won't make that (?:mistake|error) again"
            r"|note to self)",
            re.IGNORECASE,
        ),
        0.7,
    ),
],
```

Also update the `Signal` docstring (line 8) to include the new types:
```python
signal_type: str   # "decision" | "architecture" | "blocker" | "resolved_blocker" | "dependency" | "pattern" | "lesson_learned"
```

Also update `DEFAULT_CATEGORIES` in hooks-memory-capture `__init__.py` (line 11–12) to include all 7:
```python
DEFAULT_CATEGORIES: frozenset[str] = frozenset(
    {"decision", "architecture", "blocker", "resolved_blocker", "dependency", "pattern", "lesson_learned"}
)
```

**Files:**
- `modules/project-memory-core/project_memory_core/heuristics.py`
- `modules/hooks-memory-capture/amplifier_module_hooks_memory_capture/__init__.py`

**Testing:** Add tests in `tests/test_core/test_heuristics.py` for the new patterns:
- `test_dependency_added_package` — "Added package redis to requirements"
- `test_dependency_pinned_version` — "Pinned to v2.1.0 for stability"
- `test_dependency_upgraded` — "Upgraded sqlalchemy from 1.4 to 2.0"
- `test_lesson_learned_explicit` — "Lesson learned: always run migrations first"
- `test_lesson_learned_hindsight` — "In hindsight, we should have used async from the start"
- `test_lesson_learned_next_time` — "Next time we should start with the schema"

**Rules:**
- Confidence 0.7 for both (same as `architecture` — these are mid-confidence heuristics)
- Patterns must not overlap with existing `architecture` patterns (note: `architecture` already catches `added? (?:dependency|package)` — the new `dependency` patterns target package/library/module and version-specific language to differentiate)
- Existing tests must continue to pass unchanged

---

## Task 5 — Move development artifacts to `.bundlewizard/`

**Problem:** `bundle-spec.md` (24KB) and `implementation-plan.md` (53KB) are development artifacts sitting in the repo root, adding noise.

**Change:**
1. Create `.bundlewizard/` directory (does not exist yet)
2. `git mv bundle-spec.md .bundlewizard/bundle-spec.md` — this is the ORIGINAL v0.1.0 spec (567 lines). This upgrade spec is already being written to `.bundlewizard/` as the current file.
3. `git mv implementation-plan.md .bundlewizard/implementation-plan.md`

**Files:** `bundle-spec.md`, `implementation-plan.md` (move, not edit)

**Rules:**
- Use `git mv` to preserve history
- The `.bundlewizard/` directory should NOT be in `.gitignore` — these are tracked project artifacts, just not root-level clutter
- Verify no imports, tests, or bundle references point to the old paths (grep confirms: no code references these files by path)

---

## Execution Order

Tasks 1–3 are coupled (all touch bundle.md frontmatter) — apply as a single commit.
Task 4 is independent — separate commit.
Task 5 is independent — separate commit.

| Order | Tasks | Commit message |
|-------|-------|---------------|
| 1 | 1 + 2 + 3 | `fix: migrate provenance key, add schema_version, slim frontmatter` |
| 2 | 4 | `feat: add heuristic patterns for dependency and lesson_learned categories` |
| 3 | 5 | `chore: move development artifacts to .bundlewizard/` |

## Validation

After all tasks:
- `pytest` — 223/223 passing (the frontmatter line count test now passes)
- New heuristic tests add ~6 tests → ~229 total
- `ruff check` and `ruff format --check` clean
- Bundle frontmatter parses as valid YAML with correct `generated_by` key
- `extract_signals()` returns signals for all 7 configured categories
- Repo root contains only: `bundle.md`, `CHANGELOG.md`, `README.md`, `LICENSE`, `.gitignore`, and directories