"""Lightweight extraction patterns for project memory (zero LLM dependency)."""

import re
from typing import NamedTuple


class Signal(NamedTuple):
    signal_type: str  # "decision" | "architecture" | "blocker" | "resolved_blocker" | "dependency" | "pattern" | "lesson_learned"
    matched_text: str  # substring that triggered the match
    confidence: float  # 0.0–1.0


# ---------------------------------------------------------------------------
# Compiled pattern groups
# ---------------------------------------------------------------------------
# Each entry: (compiled_pattern, confidence)

SIGNAL_PATTERNS: dict[str, list[tuple[re.Pattern, float]]] = {
    "decision": [
        (
            re.compile(
                r"(?:decided to|we'll go with|the approach is"
                r"|chose \w+ over|going with|let's use|settling on)",
                re.IGNORECASE,
            ),
            0.8,
        ),
    ],
    "architecture": [
        (
            re.compile(
                r"(?:create?d? (?:file|directory)"
                r"|added? (?:dependency|package)"
                r"|schema (?:change|migration|update))",
                re.IGNORECASE,
            ),
            0.7,
        ),
    ],
    "blocker": [
        (
            re.compile(
                r"(?:blocked by|can't proceed|waiting on"
                r"|unable to|failing because)",
                re.IGNORECASE,
            ),
            0.8,
        ),
    ],
    "resolved_blocker": [
        (
            re.compile(
                r"(?:fixed|resolved|unblocked"
                r"|the issue was|root cause was|solved by)",
                re.IGNORECASE,
            ),
            0.8,
        ),
    ],
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
    "dependency": [
        (
            re.compile(
                r"(?:added? (?:library|module)\b"
                r"|installed? (?:package|library|module)"
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
}


# ---------------------------------------------------------------------------
# Extraction function
# ---------------------------------------------------------------------------


def extract_signals(text: str) -> list[Signal]:
    """Scan *text* for memory-worthy signals; return a list of Signal objects.

    Uses regex pattern groups from SIGNAL_PATTERNS.  Zero LLM calls.
    """
    if not text or not text.strip():
        return []

    results: list[Signal] = []
    for signal_type, patterns in SIGNAL_PATTERNS.items():
        for pattern, confidence in patterns:
            for match in pattern.finditer(text):
                results.append(
                    Signal(
                        signal_type=signal_type,
                        matched_text=match.group(0),
                        confidence=confidence,
                    )
                )
    return results
