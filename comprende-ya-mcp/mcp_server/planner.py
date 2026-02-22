"""Pure curriculum planner logic — no DB dependency.

Stateless planner that produces SessionPlan objects from learner state.
Operates at two timescales:
- Between sessions: full priority scoring → ordered activity list
- Within a session: lightweight threshold-based replanning
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from mcp_server.learner_model import MASTERY_THRESHOLD, PROGRESSING_THRESHOLD
from mcp_server.models import (
    Activity,
    ConceptSummary,
    ConfusionPair,
    EffectiveContext,
    PlannerProgress,
    ReplanResult,
    SessionPlan,
    StudiesState,
)

# --- Constants ---

DECAY_URGENCY_WEIGHT = 0.50
READINESS_WEIGHT = 0.30
CONFUSION_WEIGHT = 0.20

DECAY_URGENCY_THRESHOLD = 0.3  # min decay urgency to trigger review
HIGH_MASTERY_BOOST = 1.3  # boost for high-mastery decaying concepts
CONFUSION_EVIDENCE_SATURATION = 5  # evidence count at which confusion_opportunity = 1.0

ADVANCE_OUTCOME_THRESHOLD = 0.75
SCAFFOLD_OUTCOME_THRESHOLD = 0.35
MIN_REPLAN_TIME_MIN = 2.0

# Default durations per activity type (minutes)
DEFAULT_DURATIONS: dict[str, float] = {
    "review": 5.0,
    "conversation": 8.0,
    "discrimination": 6.0,
    "drill": 5.0,
}

MAX_CONCEPTS_PER_ACTIVITY = 3

# Category → default context fallback
CATEGORY_DEFAULT_CONTEXT: dict[str, str] = {
    "grammar": "structured_practice",
    "vocabulary": "casual_conversation",
    "pragmatics": "role_play",
    "discourse": "debate",
    "phonology": "pronunciation_drill",
}
DEFAULT_CONTEXT_FALLBACK = "structured_practice"

# --- Instruction Templates ---

INSTRUCTION_TEMPLATES: dict[str, str] = {
    "drill": (
        "Focus on drilling {concept_names}. "
        "Ask the learner to produce sentences using {concept_description}. "
        "Provide corrective feedback. Context: {context}."
    ),
    "conversation": (
        "Have a natural B2-level conversation about {context}. "
        "Naturally incorporate opportunities to use {concept_names}."
    ),
    "discrimination": (
        "The learner confuses {pair_a} with {pair_b}. "
        "Create minimal pair exercises in {context}."
    ),
    "review": (
        "Review {concept_names} — mastery has been declining. "
        "Start with recognition, then production. Context: {context}."
    ),
}


# --- Scoring Functions ---


def compute_decay_urgency(
    mastery: float, projected_mastery: float, practice_count: int
) -> float:
    """Compute decay urgency for a concept.

    Higher when concept is slipping. Boosted 1.3x for high-mastery concepts.
    Zero for unseen concepts (practice_count == 0).
    """
    if practice_count == 0:
        return 0.0

    drop = mastery - projected_mastery
    if drop <= 0:
        return 0.0

    urgency = min(1.0, drop / 0.3)

    if mastery >= MASTERY_THRESHOLD:
        urgency = min(1.0, urgency * HIGH_MASTERY_BOOST)

    return round(urgency, 4)


def compute_readiness(
    prerequisites: list[str],
    state_by_concept: dict[str, StudiesState],
) -> float:
    """Compute readiness based on prerequisite mastery.

    Returns 1.0 if no prerequisites.
    Hard-gated to 0 if any prerequisite below PROGRESSING_THRESHOLD.
    Otherwise, fraction of prerequisites with projected_mastery >= MASTERY_THRESHOLD.
    """
    if not prerequisites:
        return 1.0

    met = 0
    for prereq_id in prerequisites:
        state = state_by_concept.get(prereq_id)
        if state is None:
            return 0.0  # unseen prerequisite → not ready
        if state.projected_mastery < PROGRESSING_THRESHOLD:
            return 0.0  # hard gate
        if state.projected_mastery >= MASTERY_THRESHOLD:
            met += 1

    return round(met / len(prerequisites), 4)


def compute_confusion_opportunity(
    concept_id: str,
    confusion_pairs: list[ConfusionPair],
) -> float:
    """Compute confusion opportunity score.

    Returns min(1.0, evidence_count / CONFUSION_EVIDENCE_SATURATION) if concept
    is in an active confusion pair. Zero otherwise.
    """
    max_score = 0.0
    for pair in confusion_pairs:
        if concept_id in (pair.concept_a, pair.concept_b):
            score = min(1.0, pair.evidence_count / CONFUSION_EVIDENCE_SATURATION)
            max_score = max(max_score, score)
    return round(max_score, 4)


def score_concept(
    concept: ConceptSummary,
    state_by_concept: dict[str, StudiesState],
    confusion_pairs: list[ConfusionPair],
) -> float:
    """Compute overall priority score for a concept (0–1)."""
    state = state_by_concept.get(concept.id)

    if state:
        decay = compute_decay_urgency(
            state.mastery, state.projected_mastery, state.practice_count
        )
    else:
        decay = 0.0

    readiness = compute_readiness(concept.prerequisites, state_by_concept)
    confusion = compute_confusion_opportunity(concept.id, confusion_pairs)

    return round(
        DECAY_URGENCY_WEIGHT * decay
        + READINESS_WEIGHT * readiness
        + CONFUSION_WEIGHT * confusion,
        4,
    )


# --- Context Selection ---


def select_context(
    concept: ConceptSummary,
    effective_contexts: list[EffectiveContext],
) -> str:
    """Select the best communicative context for a concept.

    Filters effective_contexts by concept_id first, then falls back to
    all contexts if no concept-specific data exists.

    1. If RESPONDS_WELL_TO has entries with sample_count >= 3: pick highest effectiveness
    2. Else if any RESPONDS_WELL_TO data: pick highest effectiveness regardless
    3. Cold start fallback: category → default map
    """
    # Prefer concept-scoped contexts; fall back to all contexts
    scoped = [c for c in effective_contexts if c.concept_id == concept.id]
    pool = scoped if scoped else effective_contexts

    if pool:
        reliable = [c for c in pool if c.sample_count >= 3]
        candidates = reliable if reliable else pool
        best = max(candidates, key=lambda c: c.effectiveness)
        return best.context_id

    return CATEGORY_DEFAULT_CONTEXT.get(concept.category, DEFAULT_CONTEXT_FALLBACK)


# --- Activity Assignment ---


def _get_confusion_pair_for(
    concept_id: str, confusion_pairs: list[ConfusionPair]
) -> list[str] | None:
    """Get the contrast pair list for a concept if it's in a confusion pair."""
    for pair in confusion_pairs:
        if concept_id == pair.concept_a:
            return [pair.concept_a, pair.concept_b]
        if concept_id == pair.concept_b:
            return [pair.concept_a, pair.concept_b]
    return None


def _build_instructions(
    activity_type: str,
    concept_names: list[str],
    concept_descriptions: list[str],
    context: str,
    contrast_pair: list[str] | None = None,
) -> str:
    """Fill instruction template for an activity."""
    template = INSTRUCTION_TEMPLATES[activity_type]
    names_str = ", ".join(concept_names)
    desc_str = "; ".join(d for d in concept_descriptions if d)

    if activity_type == "discrimination" and contrast_pair:
        return template.format(
            pair_a=contrast_pair[0],
            pair_b=contrast_pair[1],
            context=context,
        )

    return template.format(
        concept_names=names_str,
        concept_description=desc_str or names_str,
        context=context,
    )


def assign_activities(
    concepts: list[ConceptSummary],
    state_by_concept: dict[str, StudiesState],
    confusion_pairs: list[ConfusionPair],
    effective_contexts: list[EffectiveContext],
    duration_target_min: float,
) -> list[Activity]:
    """Bucket scored concepts into activities, ordered by session heuristic.

    Order: review (warm-up) → advance/reinforce → discrimination.
    Max 3 concepts per activity. Trim when cumulative duration exceeds target.
    """
    # Score and sort all concepts
    scored = []
    for c in concepts:
        score = score_concept(c, state_by_concept, confusion_pairs)
        scored.append((c, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    # Bucket concepts
    review_concepts: list[ConceptSummary] = []
    advance_concepts: list[ConceptSummary] = []
    discriminate_concepts: list[ConceptSummary] = []
    reinforce_concepts: list[ConceptSummary] = []

    for concept, _score in scored:
        state = state_by_concept.get(concept.id)
        decay = (
            compute_decay_urgency(
                state.mastery, state.projected_mastery, state.practice_count
            )
            if state
            else 0.0
        )
        readiness = compute_readiness(concept.prerequisites, state_by_concept)
        confusion = compute_confusion_opportunity(concept.id, confusion_pairs)

        if confusion > 0:
            discriminate_concepts.append(concept)
        elif decay > DECAY_URGENCY_THRESHOLD:
            review_concepts.append(concept)
        elif state is None or (
            state.projected_mastery < PROGRESSING_THRESHOLD and readiness == 1.0
        ):
            advance_concepts.append(concept)
        elif state and state.projected_mastery < MASTERY_THRESHOLD:
            reinforce_concepts.append(concept)

    # Build activity list in session order
    activities: list[Activity] = []

    def _add_activities(
        bucket: list[ConceptSummary],
        activity_type: str,
    ) -> None:
        # Group into chunks of MAX_CONCEPTS_PER_ACTIVITY
        for i in range(0, len(bucket), MAX_CONCEPTS_PER_ACTIVITY):
            chunk = bucket[i : i + MAX_CONCEPTS_PER_ACTIVITY]
            # Use first concept for context selection
            context = select_context(chunk[0], effective_contexts)
            contrast_pair = None
            if activity_type == "discrimination":
                contrast_pair = _get_confusion_pair_for(chunk[0].id, confusion_pairs)

            instructions = _build_instructions(
                activity_type,
                [c.name for c in chunk],
                [c.description for c in chunk],
                context,
                contrast_pair,
            )

            activities.append(
                Activity(
                    concept_ids=[c.id for c in chunk],
                    concept_names=[c.name for c in chunk],
                    activity_type=activity_type,
                    context=context,
                    instructions=instructions,
                    duration_estimate_min=DEFAULT_DURATIONS[activity_type],
                    contrast_pair=contrast_pair,
                )
            )

    _add_activities(review_concepts, "review")
    _add_activities(advance_concepts, "conversation")
    _add_activities(reinforce_concepts, "drill")
    _add_activities(discriminate_concepts, "discrimination")

    # Trim to fit duration target
    trimmed: list[Activity] = []
    cumulative = 0.0
    for act in activities:
        if cumulative + act.duration_estimate_min > duration_target_min:
            # Include if we have no activities yet (at least one)
            if not trimmed:
                trimmed.append(act)
            break
        trimmed.append(act)
        cumulative += act.duration_estimate_min

    return trimmed


# --- Session Plan Builder ---


def build_session_plan(
    learner_id: str,
    concepts: list[ConceptSummary],
    states: list[StudiesState],
    confusion_pairs: list[ConfusionPair],
    effective_contexts: list[EffectiveContext],
    duration_target_min: float = 30.0,
) -> SessionPlan:
    """Build a complete session plan from learner state.

    Pure function — no DB access.
    """
    state_by_concept = {s.concept_id: s for s in states}

    activities = assign_activities(
        concepts,
        state_by_concept,
        confusion_pairs,
        effective_contexts,
        duration_target_min,
    )

    return SessionPlan(
        learner_id=learner_id,
        session_id=str(uuid.uuid4()),
        duration_target_min=duration_target_min,
        activities=activities,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# --- Replanning ---


def replan(
    session_plan: SessionPlan,
    progress: PlannerProgress,
) -> ReplanResult:
    """Lightweight intra-session replanning.

    Threshold-based, no re-scoring:
    - time_elapsed < 2 min → continue (too early)
    - outcome_so_far >= 0.75 → advance (drop current, move to next)
    - outcome_so_far <= 0.35 → scaffold (conversation→drill, or insert prereq review)
    - otherwise → continue
    """
    activities = list(session_plan.activities)
    idx = progress.activity_index

    if idx >= len(activities):
        return ReplanResult(
            action="continue",
            updated_activities=activities,
            reason="Activity index out of range.",
        )

    if progress.time_elapsed_min < MIN_REPLAN_TIME_MIN:
        return ReplanResult(
            action="continue",
            updated_activities=activities,
            reason=f"Too early to judge (< {MIN_REPLAN_TIME_MIN} min).",
        )

    if progress.outcome_so_far >= ADVANCE_OUTCOME_THRESHOLD:
        # Drop current activity, advance to next
        updated = activities[:idx] + activities[idx + 1 :]
        return ReplanResult(
            action="advance",
            updated_activities=updated,
            reason=(
                f"Outcome {progress.outcome_so_far:.2f} >= {ADVANCE_OUTCOME_THRESHOLD} — "
                f"advancing past activity {idx}."
            ),
        )

    if progress.outcome_so_far <= SCAFFOLD_OUTCOME_THRESHOLD:
        current = activities[idx]

        names = current.concept_names or current.concept_ids

        if current.activity_type == "conversation":
            # Replace conversation with drill
            scaffolded = current.model_copy(
                update={
                    "activity_type": "drill",
                    "instructions": _build_instructions(
                        "drill",
                        names,
                        [],
                        current.context,
                    ),
                    "duration_estimate_min": DEFAULT_DURATIONS["drill"],
                }
            )
            updated = activities[:idx] + [scaffolded] + activities[idx + 1 :]
        else:
            # Insert a prereq review before current activity
            review = Activity(
                concept_ids=current.concept_ids,
                concept_names=current.concept_names,
                activity_type="review",
                context=current.context,
                instructions=_build_instructions(
                    "review",
                    names,
                    [],
                    current.context,
                ),
                duration_estimate_min=DEFAULT_DURATIONS["review"],
            )
            updated = activities[:idx] + [review] + activities[idx:]

        return ReplanResult(
            action="scaffold",
            updated_activities=updated,
            reason=(
                f"Outcome {progress.outcome_so_far:.2f} <= {SCAFFOLD_OUTCOME_THRESHOLD} — "
                f"scaffolding activity {idx}."
            ),
        )

    return ReplanResult(
        action="continue",
        updated_activities=activities,
        reason=f"Outcome {progress.outcome_so_far:.2f} is within normal range.",
    )
