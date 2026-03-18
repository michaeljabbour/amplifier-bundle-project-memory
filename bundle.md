---
bundle:
  name: project-memory
  version: 0.1.0
  description: |
    Persistent project-scoped memory across sessions.
    Automatic capture via hooks, curated storage, session briefings.
  bundlewizard:
    packaged_at: 2026-03-18T18:57:00Z
    level_score: 0.97
    critic_verdict: PASS
    tests_passed: 223
    tests_failed: 0
    commits: 8
    upgrades:
      - date: 2026-03-18
        changes:
          - "extract _resolve_db_path into project-memory-core/paths.py (DRY)"
          - "declare project-memory-core as dependency in all module pyproject.toml"
          - "replace relative source URIs with git+https in behavior YAML"
          - "add amplifier_core test shim in conftest.py for runtime-free testing"

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
