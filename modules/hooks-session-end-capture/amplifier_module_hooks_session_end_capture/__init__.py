"""Amplifier module: session:end hook that triggers the Scribe agent to process raw captures."""

import logging
from typing import Any

from project_memory_core import MemoryStore, resolve_db_path

logger = logging.getLogger(__name__)


async def mount(
    coordinator: Any,
    config: dict[str, Any] | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    """Register a session:end handler that delegates raw capture curation to the Scribe.

    If no unprocessed captures exist the handler returns immediately without
    invoking any LLM.  When captures are present the Scribe processes them
    into curated memory entries before the session fully closes.
    """

    async def on_session_end(event: Any) -> None:  # noqa: ARG001
        """Trigger Scribe curation when unprocessed captures are waiting."""
        db_path = resolve_db_path(coordinator)

        if not db_path.exists():
            logger.debug(
                "hooks-session-end-capture: no DB at %s — skipping curation", db_path
            )
            return

        store = MemoryStore(db_path)
        try:
            unprocessed = store.count_unprocessed_captures()
            if unprocessed == 0:
                logger.debug(
                    "hooks-session-end-capture: no unprocessed captures — skipping"
                )
                return

            await coordinator.delegate(
                agent="project-memory:scribe",
                task=(
                    f"Process {unprocessed} unprocessed raw captures into "
                    "curated memory entries."
                ),
            )
            logger.info(
                "hooks-session-end-capture: delegated %d captures to scribe", unprocessed
            )

        finally:
            store.close()

    coordinator.on("session:end", on_session_end)

    logger.info("hooks-session-end-capture mounted: listening on session:end")

    return {
        "name": "hooks-session-end-capture",
        "version": "0.1.0",
        "events": ["session:end"],
    }
