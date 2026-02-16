"""Pure SM-2 spaced repetition logic (no DB dependency)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class SRState:
    ease_factor: float = 2.5
    interval_days: float = 1.0
    repetitions: int = 0
    next_review: datetime | None = None
    last_attempt: datetime | None = None


def update_sr(state: SRState, quality: int) -> SRState:
    """Update spaced repetition state using simplified SM-2.

    Args:
        state: Current SR state.
        quality: 0-5 scale (0-2 = incorrect, 3-5 = correct).

    Returns:
        New SRState with updated values.
    """
    now = datetime.now(timezone.utc)

    if quality >= 3:
        # Correct response
        if state.repetitions == 0:
            new_interval = 1.0
        elif state.repetitions == 1:
            new_interval = 6.0
        else:
            new_interval = state.interval_days * state.ease_factor

        new_ease = state.ease_factor + (
            0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        )
        new_ease = max(1.3, new_ease)
        new_reps = state.repetitions + 1
    else:
        # Incorrect response: reset
        new_interval = 1.0
        new_ease = max(1.3, state.ease_factor - 0.2)
        new_reps = 0

    return SRState(
        ease_factor=round(new_ease, 2),
        interval_days=round(new_interval, 1),
        repetitions=new_reps,
        next_review=now + timedelta(days=new_interval),
        last_attempt=now,
    )


def is_due_for_review(state: SRState) -> bool:
    """Check if a topic is due for review."""
    if state.next_review is None:
        return True
    return datetime.now(timezone.utc) >= state.next_review
