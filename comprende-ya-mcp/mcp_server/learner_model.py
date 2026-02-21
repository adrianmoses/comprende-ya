"""Pure learner-model functions — no DB dependency.

Half-life decay model replacing SM-2:
- mastery: EMA with exponential decay between practice events
- half_life_days: doubles on success, halves on failure
- confidence: function of practice count and consistency
- trend: linear slope of recent outcomes
"""

from __future__ import annotations

import math
from typing import Literal

# --- Constants ---

ALPHA = 0.3  # EMA smoothing factor
HALF_LIFE_GROWTH = 2.0  # multiplier on success
HALF_LIFE_SHRINK = 0.5  # multiplier on failure
HALF_LIFE_MIN = 0.5  # days
HALF_LIFE_MAX = 90.0  # days
HALF_LIFE_INIT = 1.0  # days
MASTERY_THRESHOLD = 0.8  # >= this ⇒ "mastered"
PROGRESSING_THRESHOLD = 0.3  # >= this ⇒ "progressing"
DECAYING_MASTERY_DROP = 0.15  # mastery - projected > this ⇒ "decaying"
SUCCESS_OUTCOME = 0.6  # outcome >= this ⇒ success for half-life
TREND_WINDOW = 5  # last N outcomes for trend
TREND_RISING = 0.05
TREND_DECLINING = -0.05
CONFUSION_OUTCOME_THRESHOLD = 0.4  # failures below this count toward confusion
CONFUSION_MIN_FAILURES = 2  # on each concept within the window
CONFUSION_WINDOW_DAYS = 14  # only count failures within this window
PROPAGATION_FACTOR = 0.2  # how much mastery delta propagates


# --- Pure functions ---


def compute_decayed_mastery(
    mastery: float, half_life_days: float, elapsed_days: float
) -> float:
    """Apply exponential decay to mastery based on elapsed time."""
    if elapsed_days <= 0 or half_life_days <= 0:
        return mastery
    return mastery * (0.5 ** (elapsed_days / half_life_days))


def recompute_studies(
    mastery: float,
    half_life_days: float,
    practice_count: int,
    outcome: float,
    elapsed_days: float,
) -> dict:
    """Recompute STUDIES edge state after a new evidence event.

    Returns dict with: mastery, half_life_days, practice_count.
    """
    # Decay current mastery to now
    decayed = compute_decayed_mastery(mastery, half_life_days, elapsed_days)

    # EMA update
    new_mastery = ALPHA * outcome + (1.0 - ALPHA) * decayed
    new_mastery = max(0.0, min(1.0, new_mastery))

    # Half-life adjustment
    if outcome >= SUCCESS_OUTCOME:
        new_hl = half_life_days * HALF_LIFE_GROWTH
    else:
        new_hl = half_life_days * HALF_LIFE_SHRINK
    new_hl = max(HALF_LIFE_MIN, min(HALF_LIFE_MAX, new_hl))

    return {
        "mastery": round(new_mastery, 4),
        "half_life_days": round(new_hl, 2),
        "practice_count": practice_count + 1,
    }


def compute_trend(
    recent_outcomes: list[float],
) -> Literal["rising", "declining", "plateau"]:
    """Linear slope of the last TREND_WINDOW outcomes."""
    outcomes = recent_outcomes[-TREND_WINDOW:]
    n = len(outcomes)
    if n < 2:
        return "plateau"

    # Simple linear regression slope
    x_mean = (n - 1) / 2.0
    y_mean = sum(outcomes) / n
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(outcomes))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return "plateau"

    slope = numerator / denominator

    if slope > TREND_RISING:
        return "rising"
    elif slope < TREND_DECLINING:
        return "declining"
    return "plateau"


def compute_confidence(practice_count: int, recent_outcomes: list[float]) -> float:
    """Confidence: 1 - 1/(1 + practice_count * consistency).

    consistency = 1 - stddev(recent_outcomes)
    """
    if practice_count == 0:
        return 0.0

    if len(recent_outcomes) < 2:
        consistency = 1.0
    else:
        mean = sum(recent_outcomes) / len(recent_outcomes)
        variance = sum((o - mean) ** 2 for o in recent_outcomes) / len(recent_outcomes)
        stddev = math.sqrt(variance)
        consistency = max(0.0, 1.0 - stddev)

    return round(1.0 - 1.0 / (1.0 + practice_count * consistency), 4)


def detect_confusions(
    concept_id: str,
    outcome: float,
    contrast_partners: list[str],
    recent_failures: dict[str, int],
) -> list[tuple[str, str]]:
    """Detect confusion pairs based on co-occurring failures.

    Args:
        concept_id: The concept that just had a failure.
        outcome: The outcome of the current event.
        contrast_partners: Concept IDs that have CONTRASTS_WITH edges.
        recent_failures: Map of concept_id -> failure count in the window.

    Returns:
        List of (concept_a, concept_b) pairs to create CONFUSES_WITH edges for.
    """
    if outcome >= CONFUSION_OUTCOME_THRESHOLD:
        return []

    # Count this failure
    my_failures = recent_failures.get(concept_id, 0) + 1

    if my_failures < CONFUSION_MIN_FAILURES:
        return []

    pairs = []
    for partner in contrast_partners:
        partner_failures = recent_failures.get(partner, 0)
        if partner_failures >= CONFUSION_MIN_FAILURES:
            # Sort to ensure consistent pair ordering
            a, b = sorted([concept_id, partner])
            pairs.append((a, b))

    return pairs


def compute_propagation(
    mastery_delta: float,
    related: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    """Compute confidence boosts for RELATED_TO neighbors.

    Args:
        mastery_delta: How much mastery increased.
        related: List of (concept_id, strength) tuples for RELATED_TO neighbors.

    Returns:
        List of (concept_id, confidence_boost) tuples.
    """
    if mastery_delta <= 0.1:
        return []

    boosts = []
    for cid, strength in related:
        boost = mastery_delta * strength * PROPAGATION_FACTOR
        if boost > 0:
            boosts.append((cid, round(boost, 4)))

    return boosts
