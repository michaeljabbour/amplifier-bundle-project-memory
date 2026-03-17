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
