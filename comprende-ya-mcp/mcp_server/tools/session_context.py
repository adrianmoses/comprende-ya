"""get_session_context tool — assemble LLM prompt context from session data."""

from __future__ import annotations

from mcp_server.db import cypher_query
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.models import SessionContext
from mcp_server.tools.concepts import query_concepts
from mcp_server.tools.learner import get_learner_profile


async def get_session_context(
    pool,
    session_id: str,
) -> SessionContext:
    """Get session context for LLM prompt enrichment.

    Fetches session details, learner profile, and concept content
    to build a suggested_prompt_additions string for the LLM.
    """
    async with pool.connection() as conn:
        # Get session details
        sessions = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (s:Session {{id: '{session_id}'}}) RETURN s",
        )

        if not sessions:
            return SessionContext(
                session_id=session_id,
                learner_summary="Session not found.",
                suggested_prompt_additions="",
            )

        session_props = (
            sessions[0].get("properties", sessions[0])
            if isinstance(sessions[0], dict)
            else sessions[0]
        )
        learner_id = session_props.get("learner_id", "")
        mode = session_props.get("mode", "free")

    # Get learner profile
    profile = await get_learner_profile(pool, learner_id)

    # Get concept content for due/struggling concepts
    concept_ids = profile.due_for_review + profile.struggling
    if not concept_ids:
        concept_ids = profile.unseen[:2]

    concept_content = []
    for cid in concept_ids[:3]:
        concepts = await query_concepts(pool, concept_id=cid)
        concept_content.extend(concepts)

    # Build learner summary
    summary_parts = [f"Learner: {profile.name} (id: {profile.learner_id})"]
    if profile.mastered:
        summary_parts.append(f"Mastered: {', '.join(profile.mastered)}")
    if profile.struggling:
        summary_parts.append(f"Struggling with: {', '.join(profile.struggling)}")
    if profile.due_for_review:
        summary_parts.append(f"Due for review: {', '.join(profile.due_for_review)}")
    if profile.unseen:
        summary_parts.append(f"Not yet studied: {', '.join(profile.unseen)}")
    learner_summary = "\n".join(summary_parts)

    # Build suggested prompt additions
    prompt_parts = []
    if mode == "structured":
        prompt_parts.append(
            "This is a structured lesson. Focus on the concepts listed below."
        )
    else:
        prompt_parts.append(
            "This is a free conversation. Gently incorporate review of weak areas."
        )

    if profile.struggling:
        prompt_parts.append(
            f"The learner is struggling with: {', '.join(profile.struggling)}. "
            "Provide extra practice and encouragement on these concepts."
        )

    for cc in concept_content:
        prompt_parts.append(f"\n--- Concept: {cc.name} ({cc.cefr_level}) ---")
        prompt_parts.append(f"Description: {cc.description}")
        if cc.mastery_signals:
            prompt_parts.append(f"Mastery signals: {', '.join(cc.mastery_signals)}")
        if cc.contrasts_with:
            prompt_parts.append(f"Contrasts with: {', '.join(cc.contrasts_with)}")

    suggested_prompt = "\n".join(prompt_parts)

    return SessionContext(
        session_id=session_id,
        learner_summary=learner_summary,
        concept_content=concept_content,
        suggested_prompt_additions=suggested_prompt,
    )
