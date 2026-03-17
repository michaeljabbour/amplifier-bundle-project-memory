"""Tests for project_memory_core.decay."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from project_memory_core.decay import (
    DEFAULT_HALF_LIFE_DAYS,
    DEFAULT_RELEVANCE_THRESHOLD,
    EXPLICIT_IMPORTANCE_MULTIPLIER,
    compute_relevance,
    is_below_threshold,
    rank_memories,
)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "")


def _days_ago(n: float) -> str:
    return _iso(datetime.now(timezone.utc) - timedelta(days=n))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_default_half_life_is_14():
    assert DEFAULT_HALF_LIFE_DAYS == 14


def test_explicit_importance_multiplier_is_1_5():
    assert EXPLICIT_IMPORTANCE_MULTIPLIER == pytest.approx(1.5)


def test_default_relevance_threshold_is_0_1():
    assert DEFAULT_RELEVANCE_THRESHOLD == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# compute_relevance — concrete values from the plan
# ---------------------------------------------------------------------------


def test_relevance_age_0_equals_importance():
    """Brand-new entry (age=0): relevance ≈ importance (no access bonus)."""
    relevance = compute_relevance(
        importance=0.8,
        created_at=_days_ago(0),
        last_accessed=None,
        access_count=0,
        source="observed",
    )
    assert relevance == pytest.approx(0.8, abs=1e-3)


def test_relevance_age_14_half_life():
    """After exactly half_life_days, relevance ≈ importance × 0.5."""
    relevance = compute_relevance(
        importance=0.8,
        created_at=_days_ago(14),
        last_accessed=None,
        access_count=0,
        source="observed",
    )
    assert relevance == pytest.approx(0.4, abs=0.01)


def test_relevance_age_28_two_half_lives():
    """After 2× half_life_days, relevance ≈ importance × 0.25."""
    relevance = compute_relevance(
        importance=0.8,
        created_at=_days_ago(28),
        last_accessed=None,
        access_count=0,
        source="observed",
    )
    assert relevance == pytest.approx(0.2, abs=0.01)


def test_relevance_explicit_source_gets_multiplier():
    """Explicit entries: effective_importance = min(importance × 1.5, 1.0)."""
    # 0.6 × 1.5 = 0.9; after 14 days → 0.45
    relevance = compute_relevance(
        importance=0.6,
        created_at=_days_ago(14),
        last_accessed=None,
        access_count=0,
        source="explicit",
    )
    assert relevance == pytest.approx(0.45, abs=0.01)


def test_relevance_explicit_importance_capped_at_1():
    """effective_importance is capped at 1.0 (0.8 × 1.5 = 1.2 → 1.0)."""
    relevance_explicit = compute_relevance(
        importance=0.8,
        created_at=_days_ago(0),
        last_accessed=None,
        access_count=0,
        source="explicit",
    )
    # capped at 1.0; age=0 → 1.0
    assert relevance_explicit == pytest.approx(1.0, abs=1e-3)


def test_relevance_observed_source_normal_rate():
    """Observed entries decay at normal rate (multiplier=1.0)."""
    relevance = compute_relevance(
        importance=0.6,
        created_at=_days_ago(14),
        last_accessed=None,
        access_count=0,
        source="observed",
    )
    assert relevance == pytest.approx(0.3, abs=0.01)


def test_relevance_uses_last_accessed_over_created_at():
    """Decay clock resets to last_accessed when provided."""
    # created 28 days ago but last accessed 0 days ago → should be ≈ importance
    relevance = compute_relevance(
        importance=0.8,
        created_at=_days_ago(28),
        last_accessed=_days_ago(0),
        access_count=0,
        source="observed",
    )
    assert relevance == pytest.approx(0.8, abs=0.02)


def test_relevance_access_bonus_increases_score():
    """Higher access_count produces a small upward boost."""
    base = compute_relevance(
        importance=0.5,
        created_at=_days_ago(7),
        last_accessed=None,
        access_count=0,
        source="observed",
    )
    boosted = compute_relevance(
        importance=0.5,
        created_at=_days_ago(7),
        last_accessed=None,
        access_count=10,
        source="observed",
    )
    assert boosted > base


def test_relevance_access_bonus_is_logarithmic():
    """access bonus = 0.05 × log2(1 + access_count)."""
    # access_count=3: bonus = 0.05 × log2(4) = 0.05 × 2 = 0.10
    importance = 0.5
    created_at = _days_ago(0)
    base = compute_relevance(importance, created_at, None, 0, "observed")
    with_access = compute_relevance(importance, created_at, None, 3, "observed")
    expected_bonus = 0.05 * math.log2(1 + 3)
    assert with_access == pytest.approx(min(base + expected_bonus, 1.0), abs=1e-6)


def test_relevance_capped_at_1_0():
    """Total relevance never exceeds 1.0 even with access bonus."""
    relevance = compute_relevance(
        importance=0.99,
        created_at=_days_ago(0),
        last_accessed=None,
        access_count=1000,
        source="explicit",
    )
    assert relevance <= 1.0


def test_relevance_non_negative():
    """Relevance is never negative."""
    relevance = compute_relevance(
        importance=0.01,
        created_at=_days_ago(365),
        last_accessed=None,
        access_count=0,
        source="observed",
    )
    assert relevance >= 0.0


def test_relevance_returns_float():
    """compute_relevance returns a float."""
    result = compute_relevance(0.5, _days_ago(7), None, 0, "observed")
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# is_below_threshold
# ---------------------------------------------------------------------------


def test_is_below_threshold_true():
    assert is_below_threshold(0.05) is True


def test_is_below_threshold_false():
    assert is_below_threshold(0.5) is False


def test_is_below_threshold_at_boundary():
    """Exactly at threshold is NOT below it."""
    assert is_below_threshold(0.1, threshold=0.1) is False


def test_is_below_threshold_custom_threshold():
    assert is_below_threshold(0.25, threshold=0.3) is True
    assert is_below_threshold(0.35, threshold=0.3) is False


# ---------------------------------------------------------------------------
# rank_memories
# ---------------------------------------------------------------------------


def _make_memory(importance: float, age_days: float, source: str = "observed") -> dict:
    return {
        "id": f"mem-{importance}-{age_days}",
        "importance": importance,
        "created_at": _days_ago(age_days),
        "last_accessed": None,
        "access_count": 0,
        "source": source,
    }


def test_rank_memories_returns_sorted_descending():
    """rank_memories returns entries sorted by current_relevance descending."""
    memories = [
        _make_memory(0.8, 28),   # old, low relevance
        _make_memory(0.8, 0),    # new, high relevance
        _make_memory(0.8, 14),   # mid
    ]
    ranked = rank_memories(memories)
    scores = [m["current_relevance"] for m in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_memories_adds_current_relevance_field():
    """rank_memories injects current_relevance into each entry."""
    memories = [_make_memory(0.8, 7)]
    ranked = rank_memories(memories)
    assert "current_relevance" in ranked[0]
    assert isinstance(ranked[0]["current_relevance"], float)


def test_rank_memories_does_not_mutate_original_list():
    """rank_memories returns a new list; originals are not mutated."""
    m = _make_memory(0.5, 10)
    originals = [m]
    rank_memories(originals)
    assert "current_relevance" not in m


def test_rank_memories_empty_input():
    """rank_memories handles empty list."""
    assert rank_memories([]) == []


def test_rank_memories_explicit_beats_observed_same_age():
    """Explicit source ranks higher than observed at same age/importance."""
    observed = _make_memory(0.6, 14, source="observed")
    explicit = _make_memory(0.6, 14, source="explicit")
    ranked = rank_memories([observed, explicit])
    assert ranked[0]["source"] == "explicit"
