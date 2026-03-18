"""Shared path resolution for the project memory database.

All hook modules and the tool module need to locate the memory database.
This module provides a single implementation to avoid copy-paste drift.
"""

from pathlib import Path
from typing import Any


def resolve_db_path(coordinator: Any, *, create_dir: bool = False) -> Path:
    """Determine the memory DB path from the coordinator's project root.

    Tries coordinator.project_root, then coordinator.context['project_root'],
    then falls back to Path.cwd().

    Args:
        coordinator: The Amplifier coordinator object.
        create_dir: If True, create the parent directory if absent.
            Use True for write-path hooks (memory capture).
            Use False for read-path hooks (briefing, session-end) that
            should skip silently when no DB exists.

    Returns:
        Path to the memory.db file.
    """
    project_root: Any = getattr(coordinator, "project_root", None)
    if project_root is None:
        context: dict[str, Any] = getattr(coordinator, "context", {}) or {}
        project_root = context.get("project_root", Path.cwd())

    db_dir = Path(project_root) / ".amplifier" / "project-memory"
    if create_dir:
        db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "memory.db"
