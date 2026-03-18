"""Amplifier module: hooks for capturing tool and prompt events into the raw memory buffer."""

import logging
from typing import Any

from project_memory_core import MemoryStore, extract_signals, resolve_db_path

logger = logging.getLogger(__name__)

# All signal types the heuristics can detect
DEFAULT_CATEGORIES: frozenset[str] = frozenset(
    {"decision", "architecture", "blocker", "resolved_blocker", "pattern"}
)


def _extract_text(event: Any) -> str | None:
    """Extract a text string from a coordinator event object or dict.

    Tries common attribute names in priority order, then falls back to
    str(event) only if the result looks like real content (not a repr).
    """
    for attr in ("text", "content", "result", "output", "data"):
        value = getattr(event, attr, None)
        if isinstance(value, str) and value.strip():
            return value

    if isinstance(event, dict):
        for key in ("text", "content", "result", "output", "data"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                return value

    # Last-resort: coerce to string, but skip Python object reprs
    raw = str(event)
    if raw and not raw.startswith("<"):
        return raw

    return None


async def mount(
    coordinator: Any,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register tool:post and prompt:complete handlers for heuristic signal capture.

    Zero LLM cost — all extraction is regex-based.  Signals above
    ``min_confidence`` are written to the raw_captures table for later
    curation by the Scribe agent at session end.
    """
    config = config or {}
    db_path = resolve_db_path(coordinator, create_dir=True)
    store = MemoryStore(db_path)

    min_confidence: float = config.get("min_confidence", 0.5)
    categories: set[str] = set(config.get("categories", list(DEFAULT_CATEGORIES)))

    async def on_tool_post(event: Any) -> None:
        """Extract signals from tool result payloads."""
        text = _extract_text(event)
        if not text:
            return

        signals = extract_signals(text)
        session_id: str | None = getattr(event, "session_id", None)
        if isinstance(event, dict):
            session_id = session_id or event.get("session_id")

        for signal in signals:
            if signal.confidence >= min_confidence and signal.signal_type in categories:
                store.add_raw_capture(
                    event_type="tool:post",
                    raw_content=text,
                    signal_type=signal.signal_type,
                    confidence=signal.confidence,
                    session_id=session_id,
                )

    async def on_prompt_complete(event: Any) -> None:
        """Extract signals from prompt completion payloads."""
        text = _extract_text(event)
        if not text:
            return

        signals = extract_signals(text)
        session_id = getattr(event, "session_id", None)
        if isinstance(event, dict):
            session_id = session_id or event.get("session_id")

        for signal in signals:
            if signal.confidence >= min_confidence and signal.signal_type in categories:
                store.add_raw_capture(
                    event_type="prompt:complete",
                    raw_content=text,
                    signal_type=signal.signal_type,
                    confidence=signal.confidence,
                    session_id=session_id,
                )

    coordinator.on("tool:post", on_tool_post)
    coordinator.on("prompt:complete", on_prompt_complete)

    logger.info(
        "hooks-memory-capture mounted: listening on tool:post, prompt:complete "
        "(min_confidence=%.2f, categories=%s)",
        min_confidence,
        sorted(categories),
    )

    return {
        "name": "hooks-memory-capture",
        "version": "0.1.0",
        "events": ["tool:post", "prompt:complete"],
    }
