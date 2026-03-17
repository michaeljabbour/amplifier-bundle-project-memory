"""Decay model: half-life computation and importance multiplier for memory entries."""

import math
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_HALF_LIFE_DAYS: int = 14
EXPLICIT_IMPORTANCE_MULTIPLIER: float = 1.5
DEFAULT_RELEVANCE_THRESHOLD: float = 0.1


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp (with or without trailing Z/offset)."""
    ts = ts.rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            dt = datetime.strptime(ts, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {ts!r}")


def _age_days(created_at: str, last_accessed: str | None) -> float:
    """Return days since last_accessed (or created_at if None)."""
    anchor_str = last_accessed if last_accessed else created_at
    anchor = _parse_iso(anchor_str)
    now = datetime.now(timezone.utc)
    delta = now - anchor
    return max(delta.total_seconds() / 86400.0, 0.0)


# ---------------------------------------------------------------------------
# Core scoring function
# ---------------------------------------------------------------------------


def compute_relevance(
    importance: float,
    created_at: str,
    last_accessed: str | None,
    access_count: int,
    source: str,
    half_life_days: int = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """Compute current relevance score for a single memory entry (0.0–1.0).

    Formula:
        effective_importance = min(importance × multiplier, 1.0)
        relevance = effective_importance × (0.5 ^ (age_days / half_life_days))
                    + 0.05 × log2(1 + access_count)   [capped at 1.0]
    """
    multiplier = EXPLICIT_IMPORTANCE_MULTIPLIER if source == "explicit" else 1.0
    effective_importance = min(importance * multiplier, 1.0)

    age = _age_days(created_at, last_accessed)
    decay_factor = 0.5 ** (age / half_life_days)

    base_relevance = effective_importance * decay_factor
    access_bonus = 0.05 * math.log2(1 + access_count)

    return min(base_relevance + access_bonus, 1.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_below_threshold(
    relevance: float,
    threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
) -> bool:
    """Return True iff relevance is strictly below the threshold."""
    return relevance < threshold


def rank_memories(
    memories: list[dict[str, Any]],
    half_life_days: int = DEFAULT_HALF_LIFE_DAYS,
) -> list[dict[str, Any]]:
    """Return a new list sorted by current relevance (descending).

    Adds ``current_relevance`` key to each copy; originals are not mutated.
    """
    results: list[dict[str, Any]] = []
    for m in memories:
        score = compute_relevance(
            importance=m["importance"],
            created_at=m["created_at"],
            last_accessed=m.get("last_accessed"),
            access_count=m.get("access_count", 0),
            source=m.get("source", "observed"),
            half_life_days=half_life_days,
        )
        results.append({**m, "current_relevance": score})
    results.sort(key=lambda e: e["current_relevance"], reverse=True)
    return results
