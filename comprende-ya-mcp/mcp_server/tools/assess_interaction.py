"""assess_interaction tool — LLM-as-judge assessment of conversation transcripts."""

from __future__ import annotations

from mcp_server.assessment import run_assessment
from mcp_server.models import InteractionTurn


async def assess_interaction(
    pool,
    learner_id: str,
    session_id: str,
    turns: list[dict],
    target_concept_ids: list[str] | None = None,
) -> dict:
    """Assess a conversation transcript against concept mastery signals.

    Each turn: {role: "learner"|"teacher", text: str, timestamp?: str, turn_index?: int}
    Returns AssessmentResult as dict.
    """
    parsed_turns = [InteractionTurn(**t) for t in turns]

    # Auto-assign turn_index if all are 0
    if all(t.turn_index == 0 for t in parsed_turns) and len(parsed_turns) > 1:
        for i, t in enumerate(parsed_turns):
            t.turn_index = i

    result = await run_assessment(
        pool,
        learner_id=learner_id,
        session_id=session_id,
        turns=parsed_turns,
        target_concept_ids=target_concept_ids,
    )
    return result.model_dump()
