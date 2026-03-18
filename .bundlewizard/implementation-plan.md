# project-memory v0.1.0 → v0.1.1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve all 5 audit findings from the v0.1.0 bundle review — fix the 1 failing test, complete heuristic coverage, and tidy the repo.

**Architecture:** No redesign. This is surgical renovation across 3 independent commits. Commit 1 fixes frontmatter (Tasks 1–3, coupled — they all edit `bundle.md`). Commit 2 adds missing heuristic patterns (Task 4). Commit 3 moves dev artifacts out of the repo root (Task 5).

**Tech Stack:** Python 3.12, pytest, YAML frontmatter, regex, git

**Spec:** `.bundlewizard/bundle-spec.md` — all line references below point there.

---

## Commit 1: Frontmatter Renovation (Tasks 1–3)

These three tasks are coupled — they all modify `bundle.md` frontmatter and must land as one atomic commit. The order below is the safe editing order (each step builds on the previous).

---

### Task 1: Migrate provenance key `bundlewizard` → `generated_by`

**Files:**
- Modify: `bundle.md` (lines 8–14)

**Step 1: Edit `bundle.md` — rename key and add `tool:` child**

Replace lines 8–14 of `bundle.md`:

```yaml
  bundlewizard:
    packaged_at: 2026-03-18T18:57:00Z
    level_score: 0.97
    critic_verdict: PASS
    tests_passed: 223
    tests_failed: 0
    commits: 8
```

With:

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

Changes:
- `bundlewizard:` → `generated_by:`
- Insert `tool: bundlewizard` as first child key (2-space indent under `generated_by`)
- All other child values stay identical
- Do NOT touch the `upgrades:` array yet — Task 3 handles that

**Step 2: Verify YAML still parses**

Run:
```bash
python3 -c "
import yaml
content = open('bundle.md').read()
fm = content.split('---', 2)[1]
data = yaml.safe_load(fm)
gb = data['bundle']['generated_by']
assert gb['tool'] == 'bundlewizard', f'Expected bundlewizard, got {gb[\"tool\"]}'
assert gb['packaged_at'] is not None
assert gb['tests_passed'] == 223
print('OK: generated_by key is correct')
"
```
Expected: `OK: generated_by key is correct`

---

### Task 2: Add `schema_version: 1` to frontmatter

**Files:**
- Modify: `bundle.md` (line 3 — insert before `name:`)

**Step 1: Insert `schema_version: 1` as first child of `bundle:`**

Current (after Task 1, lines 2–4):
```yaml
bundle:
  name: project-memory
  version: 0.1.0
```

Target:
```yaml
bundle:
  schema_version: 1
  name: project-memory
  version: 0.1.0
```

Insert `  schema_version: 1` on a new line immediately after `bundle:` and before `  name:`.

**Step 2: Verify schema_version parses as integer**

Run:
```bash
python3 -c "
import yaml
content = open('bundle.md').read()
fm = content.split('---', 2)[1]
data = yaml.safe_load(fm)
sv = data['bundle']['schema_version']
assert sv == 1 and isinstance(sv, int), f'Expected int 1, got {type(sv).__name__} {sv}'
print('OK: schema_version is integer 1')
"
```
Expected: `OK: schema_version is integer 1`

---

### Task 3: Slim frontmatter — remove `upgrades` array, drop `tests_failed: 0`, create CHANGELOG.md

**Files:**
- Modify: `bundle.md` (remove `upgrades:` block + `tests_failed: 0` line)
- Create: `CHANGELOG.md`

**Step 1: Remove `tests_failed: 0` from `bundle.md`**

Delete this line entirely (it is a child of `generated_by`):
```yaml
    tests_failed: 0
```

This is redundant — `tests_passed: 223` is sufficient.

**Step 2: Remove the entire `upgrades:` block from `bundle.md`**

Delete these lines (children of `generated_by`):
```yaml
    upgrades:
      - date: 2026-03-18
        changes:
          - "extract _resolve_db_path into project-memory-core/paths.py (DRY)"
          - "declare project-memory-core as dependency in all module pyproject.toml"
          - "replace relative source URIs with git+https in behavior YAML"
          - "add amplifier_core test shim in conftest.py for runtime-free testing"
```

**Step 3: Verify the complete frontmatter matches the target**

After Tasks 1–3, the full `bundle.md` frontmatter (between `---` delimiters) must be exactly:

```yaml
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
```

Run:
```bash
python3 -c "
content = open('bundle.md').read()
fm = content.split('---', 2)[1]
non_empty = [ln for ln in fm.split('\n') if ln.strip()]
print(f'Non-empty frontmatter lines: {len(non_empty)}')
assert len(non_empty) <= 20, f'FAIL: {len(non_empty)} lines exceeds 20-line limit'
assert len(non_empty) <= 18, f'WARNING: {len(non_empty)} lines — target was ≤18'
print('OK: frontmatter is within limits')
"
```
Expected: `Non-empty frontmatter lines: 17` then `OK: frontmatter is within limits`

(17 lines, well within the ≤20 test limit and the ≤18 target.)

**Step 4: Create `CHANGELOG.md` in the repo root**

Create the file `CHANGELOG.md` with this exact content:

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

**Step 5: Run the failing test to confirm it passes now**

Run:
```bash
cd /Users/michaeljabbour/dev/amplifier-bundle-project-memory
python3 -m pytest tests/test_composition/test_structural.py::TestThinBundlePattern::test_frontmatter_line_count -v
```
Expected: `PASSED` (was `FAILED` before — this was the 1 failing test out of 223)

**Step 6: Run the full test suite to check for regressions**

Run:
```bash
python3 -m pytest --tb=short -q
```
Expected: `222 passed` (or `223 passed` if the frontmatter test was counted — total should be all green, 0 failures)

**Step 7: Lint check**

Run:
```bash
python3 -m ruff check . && python3 -m ruff format --check .
```
Expected: No errors, no format changes needed. (We only touched YAML/Markdown in this commit.)

**Step 8: Commit**

```bash
git add bundle.md CHANGELOG.md
git commit -m "fix: migrate provenance key, add schema_version, slim frontmatter"
```

---

## Commit 2: Add Missing Heuristic Patterns (Task 4)

This commit is independent of Commit 1. It adds `dependency` and `lesson_learned` regex patterns so `extract_signals()` can emit all 7 categories configured in the behavior YAML.

---

### Task 4a: Write the failing tests for `dependency` signals

**Files:**
- Modify: `tests/test_core/test_heuristics.py` (append after line 238, before the "Case insensitivity" section)

**Step 1: Add dependency signal tests**

Insert a new test section after the "Pattern signals" section (after line 238) and before the "Case insensitivity" section (line 240). Find this marker:

```python
# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------
```

Insert the following block immediately **before** that marker:

```python
# ---------------------------------------------------------------------------
# Dependency signals
# ---------------------------------------------------------------------------


def test_dependency_added_package():
    """'Added package redis to requirements' triggers dependency signal."""
    sigs = extract_signals("Added package redis to requirements")
    dep_sigs = _by_type(sigs, "dependency")
    assert len(dep_sigs) >= 1
    assert dep_sigs[0].confidence >= 0.6


def test_dependency_pinned_version():
    """'Pinned to v2.1.0 for stability' triggers dependency signal."""
    sigs = extract_signals("Pinned to v2.1.0 for stability")
    assert any(s.signal_type == "dependency" for s in sigs)


def test_dependency_upgraded():
    """'Upgraded sqlalchemy from 1.4 to 2.0' triggers dependency signal."""
    sigs = extract_signals("Upgraded sqlalchemy from 1.4 to 2.0")
    assert any(s.signal_type == "dependency" for s in sigs)


# ---------------------------------------------------------------------------
# Lesson-learned signals
# ---------------------------------------------------------------------------


def test_lesson_learned_explicit():
    """'Lesson learned: always run migrations first' triggers lesson_learned signal."""
    sigs = extract_signals("Lesson learned: always run migrations first")
    ll_sigs = _by_type(sigs, "lesson_learned")
    assert len(ll_sigs) >= 1
    assert ll_sigs[0].confidence >= 0.6


def test_lesson_learned_hindsight():
    """'In hindsight, we should have used async' triggers lesson_learned signal."""
    sigs = extract_signals("In hindsight, we should have used async from the start")
    assert any(s.signal_type == "lesson_learned" for s in sigs)


def test_lesson_learned_next_time():
    """'Next time we should start with the schema' triggers lesson_learned signal."""
    sigs = extract_signals("Next time we should start with the schema")
    assert any(s.signal_type == "lesson_learned" for s in sigs)


```

**Step 2: Run the new tests to verify they fail**

Run:
```bash
python3 -m pytest tests/test_core/test_heuristics.py::test_dependency_added_package tests/test_core/test_heuristics.py::test_dependency_pinned_version tests/test_core/test_heuristics.py::test_dependency_upgraded tests/test_core/test_heuristics.py::test_lesson_learned_explicit tests/test_core/test_heuristics.py::test_lesson_learned_hindsight tests/test_core/test_heuristics.py::test_lesson_learned_next_time -v
```
Expected: All 6 FAIL (no `dependency` or `lesson_learned` keys in `SIGNAL_PATTERNS` yet)

---

### Task 4b: Add `dependency` and `lesson_learned` patterns to heuristics.py

**Files:**
- Modify: `modules/project-memory-core/project_memory_core/heuristics.py` (lines 8, 60–70)

**Step 1: Update the `Signal` docstring to list all 7 types**

In `heuristics.py` line 8, replace:

```python
    signal_type: str   # "decision" | "architecture" | "blocker" | "resolved_blocker" | "pattern"
```

With:

```python
    signal_type: str   # "decision" | "architecture" | "blocker" | "resolved_blocker" | "dependency" | "pattern" | "lesson_learned"
```

**Step 2: Add `dependency` and `lesson_learned` entries to `SIGNAL_PATTERNS`**

In `heuristics.py`, find the `"pattern"` entry (lines 60–69):

```python
    "pattern": [
        (
            re.compile(
                r"(?:keep (?:running into|seeing)|every time"
                r"|recurring|pattern of)",
                re.IGNORECASE,
            ),
            0.6,
        ),
    ],
```

Insert the following two entries **after** the `"pattern"` entry and **before** the closing `}` of `SIGNAL_PATTERNS`:

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

The final `SIGNAL_PATTERNS` dict should have 7 keys: `decision`, `architecture`, `blocker`, `resolved_blocker`, `pattern`, `dependency`, `lesson_learned`.

**Step 3: Run the new tests to verify they pass**

Run:
```bash
python3 -m pytest tests/test_core/test_heuristics.py::test_dependency_added_package tests/test_core/test_heuristics.py::test_dependency_pinned_version tests/test_core/test_heuristics.py::test_dependency_upgraded tests/test_core/test_heuristics.py::test_lesson_learned_explicit tests/test_core/test_heuristics.py::test_lesson_learned_hindsight tests/test_core/test_heuristics.py::test_lesson_learned_next_time -v
```
Expected: All 6 PASSED

---

### Task 4c: Update `DEFAULT_CATEGORIES` in hooks-memory-capture

**Files:**
- Modify: `modules/hooks-memory-capture/amplifier_module_hooks_memory_capture/__init__.py` (lines 11–13)

**Step 1: Add the 2 missing categories to the frozenset**

Replace lines 11–13:

```python
DEFAULT_CATEGORIES: frozenset[str] = frozenset(
    {"decision", "architecture", "blocker", "resolved_blocker", "pattern"}
)
```

With:

```python
DEFAULT_CATEGORIES: frozenset[str] = frozenset(
    {"decision", "architecture", "blocker", "resolved_blocker", "dependency", "pattern", "lesson_learned"}
)
```

This ensures that when no `categories` config is passed, the hook still filters for all 7 categories (matching the behavior YAML's configured set).

**Step 2: Run the full test suite**

Run:
```bash
python3 -m pytest --tb=short -q
```
Expected: All tests pass (the original 223 + the 6 new ones = 229 passed, 0 failures)

**Step 3: Lint check**

Run:
```bash
python3 -m ruff check modules/project-memory-core/project_memory_core/heuristics.py modules/hooks-memory-capture/amplifier_module_hooks_memory_capture/__init__.py tests/test_core/test_heuristics.py
python3 -m ruff format --check modules/project-memory-core/project_memory_core/heuristics.py modules/hooks-memory-capture/amplifier_module_hooks_memory_capture/__init__.py tests/test_core/test_heuristics.py
```
Expected: No errors, no format changes needed.

**Step 4: Commit**

```bash
git add modules/project-memory-core/project_memory_core/heuristics.py \
       modules/hooks-memory-capture/amplifier_module_hooks_memory_capture/__init__.py \
       tests/test_core/test_heuristics.py
git commit -m "feat: add heuristic patterns for dependency and lesson_learned categories"
```

---

## Commit 3: Move Development Artifacts (Task 5)

This commit is independent of Commits 1 and 2. It moves large dev-only files out of the repo root.

---

### Task 5: Move `bundle-spec.md` and `implementation-plan.md` into `.bundlewizard/`

**Files:**
- Move: `bundle-spec.md` → `.bundlewizard/bundle-spec.md`
- Move: `implementation-plan.md` → `.bundlewizard/implementation-plan.md`

**Important context:** The `.bundlewizard/` directory already exists and already contains the v0.1.1 upgrade spec (`bundle-spec.md` — the file currently at `.bundlewizard/bundle-spec.md`). The root-level `bundle-spec.md` is the *original v0.1.0 spec* (567 lines, 24KB). We need to handle the name collision.

**Step 1: Rename the existing v0.1.0 spec to avoid collision**

The root `bundle-spec.md` (v0.1.0, 24KB) would collide with `.bundlewizard/bundle-spec.md` (v0.1.1 upgrade spec, already there). Rename the v0.1.0 spec first:

```bash
git mv bundle-spec.md .bundlewizard/bundle-spec-v0.1.0.md
```

**Step 2: Move the implementation plan**

The root `implementation-plan.md` (53KB) is the v0.1.0 implementation plan. Move it:

```bash
git mv implementation-plan.md .bundlewizard/implementation-plan-v0.1.0.md
```

**Step 3: Verify no code references the old paths**

Run:
```bash
grep -rn "bundle-spec\.md\|implementation-plan\.md" --include="*.py" --include="*.yaml" --include="*.yml" --include="*.toml" .
```
Expected: No matches. (The only reference was inside `implementation-plan.md` itself — which has been moved.)

Also verify the `.bundlewizard/` directory is NOT in `.gitignore`:
```bash
grep -n "bundlewizard" .gitignore 2>/dev/null || echo "OK: not in .gitignore"
```
Expected: `OK: not in .gitignore`

**Step 4: Run the full test suite**

Run:
```bash
python3 -m pytest --tb=short -q
```
Expected: All 229 tests pass (no test references these files by path).

**Step 5: Commit**

```bash
git add -A
git commit -m "chore: move development artifacts to .bundlewizard/"
```

---

## Final Validation Checklist

After all 3 commits, run these checks to confirm everything is green:

**1. Full test suite:**
```bash
python3 -m pytest -v
```
Expected: 229 passed, 0 failed (223 original + 6 new heuristic tests)

**2. The previously-failing test now passes:**
```bash
python3 -m pytest tests/test_composition/test_structural.py::TestThinBundlePattern::test_frontmatter_line_count -v
```
Expected: PASSED

**3. Lint + format clean:**
```bash
python3 -m ruff check . && python3 -m ruff format --check .
```
Expected: No errors

**4. Frontmatter parses with correct keys:**
```bash
python3 -c "
import yaml
content = open('bundle.md').read()
fm = content.split('---', 2)[1]
data = yaml.safe_load(fm)
b = data['bundle']
assert b['schema_version'] == 1
assert b['name'] == 'project-memory'
assert 'generated_by' in b
assert b['generated_by']['tool'] == 'bundlewizard'
assert 'bundlewizard' not in b  # old key is gone
print('OK: frontmatter structure is correct')
"
```

**5. All 7 categories produce signals:**
```bash
python3 -c "
from project_memory_core.heuristics import SIGNAL_PATTERNS
expected = {'decision', 'architecture', 'blocker', 'resolved_blocker', 'dependency', 'pattern', 'lesson_learned'}
actual = set(SIGNAL_PATTERNS.keys())
assert actual == expected, f'Missing: {expected - actual}, Extra: {actual - expected}'
print(f'OK: SIGNAL_PATTERNS has all {len(actual)} categories')
"
```

**6. DEFAULT_CATEGORIES matches SIGNAL_PATTERNS:**
```bash
python3 -c "
from project_memory_core.heuristics import SIGNAL_PATTERNS
from amplifier_module_hooks_memory_capture import DEFAULT_CATEGORIES
sp_keys = set(SIGNAL_PATTERNS.keys())
assert DEFAULT_CATEGORIES == frozenset(sp_keys), f'Mismatch: SIGNAL_PATTERNS={sp_keys}, DEFAULT_CATEGORIES={DEFAULT_CATEGORIES}'
print(f'OK: DEFAULT_CATEGORIES matches SIGNAL_PATTERNS ({len(DEFAULT_CATEGORIES)} categories)')
"
```

**7. Repo root is tidy:**
```bash
ls -1 *.md
```
Expected: `bundle.md`, `CHANGELOG.md`, `README.md` (no `bundle-spec.md` or `implementation-plan.md`)

**8. Git log shows 3 clean commits:**
```bash
git log --oneline -3
```
Expected:
```
<hash> chore: move development artifacts to .bundlewizard/
<hash> feat: add heuristic patterns for dependency and lesson_learned categories
<hash> fix: migrate provenance key, add schema_version, slim frontmatter
```
