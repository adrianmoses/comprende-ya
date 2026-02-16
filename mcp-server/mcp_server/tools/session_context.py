"""get_session_context tool — assemble LLM prompt context from session data."""

from __future__ import annotations

from mcp_server.db import cypher_query
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.models import SessionContext
from mcp_server.tools.curriculum import query_curriculum
from mcp_server.tools.learner import get_learner_profile


async def get_session_context(
    pool,
    session_id: str,
) -> SessionContext:
    """Get session context for LLM prompt enrichment.

    Fetches session details, learner profile, and topic content
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

    # Get topic content for due/struggling topics
    topic_ids = profile.due_for_review + profile.struggling
    if not topic_ids:
        topic_ids = profile.unseen[:2]

    topic_content = []
    for tid in topic_ids[:3]:
        topics = await query_curriculum(pool, topic_id=tid)
        topic_content.extend(topics)

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
            "This is a structured lesson. Focus on the topics listed below."
        )
    else:
        prompt_parts.append(
            "This is a free conversation. Gently incorporate review of weak areas."
        )

    if profile.struggling:
        prompt_parts.append(
            f"The learner is struggling with: {', '.join(profile.struggling)}. "
            "Provide extra practice and encouragement on these topics."
        )

    for tc in topic_content:
        prompt_parts.append(f"\n--- Topic: {tc.name} ({tc.level}) ---")
        if tc.vocabulary:
            vocab_strs = [
                f"  {v.get('word_es', '')} = {v.get('word_en', '')}"
                for v in tc.vocabulary
            ]
            prompt_parts.append("Vocabulary:\n" + "\n".join(vocab_strs))
        if tc.grammar_rules:
            for g in tc.grammar_rules:
                prompt_parts.append(
                    f"Grammar: {g.get('name', '')} — {g.get('explanation_es', '')}"
                )
        if tc.phrases:
            phrase_strs = [
                f"  {p.get('phrase_es', '')} = {p.get('phrase_en', '')}"
                for p in tc.phrases
            ]
            prompt_parts.append("Phrases:\n" + "\n".join(phrase_strs))

    suggested_prompt = "\n".join(prompt_parts)

    return SessionContext(
        session_id=session_id,
        learner_summary=learner_summary,
        topic_content=topic_content,
        suggested_prompt_additions=suggested_prompt,
    )
