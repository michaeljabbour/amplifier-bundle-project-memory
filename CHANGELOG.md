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
