"""get_learner_profile tool — summarize learner's progress."""

from __future__ import annotations

from mcp_server.db import cypher_query
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.models import LearnerProfile


async def get_learner_profile(pool, learner_id: str) -> LearnerProfile:
    """Get a learner's profile with categorized topics.

    Categories:
    - mastered: topics with MASTERED edge
    - struggling: topics with STRUGGLED_WITH edge
    - due_for_review: topics in SR table where next_review <= now
    - unseen: all other topics
    """
    async with pool.connection() as conn:
        # Get learner name
        learners = await cypher_query(
            conn, GRAPH_NAME, f"MATCH (l:Learner {{id: '{learner_id}'}}) RETURN l"
        )
        name = learner_id
        if learners:
            props = (
                learners[0].get("properties", learners[0])
                if isinstance(learners[0], dict)
                else learners[0]
            )
            name = props.get("name", learner_id)

        # Mastered topics
        mastered_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (l:Learner {{id: '{learner_id}'}})-[:MASTERED]->(t:Topic) RETURN t",
        )
        mastered = []
        for m in mastered_rows:
            props = m.get("properties", m) if isinstance(m, dict) else m
            mastered.append(props.get("id", ""))

        # Struggling topics
        struggled_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (l:Learner {{id: '{learner_id}'}})-[:STRUGGLED_WITH]->(t:Topic) RETURN t",
        )
        struggling = []
        for s in struggled_rows:
            props = s.get("properties", s) if isinstance(s, dict) else s
            struggling.append(props.get("id", ""))

        # Due for review
        row = await conn.execute(
            "SELECT topic_id FROM spaced_repetition "
            "WHERE learner_id = %s AND next_review <= now()",
            (learner_id,),
        )
        due_rows = await row.fetchall()
        due_for_review = [r[0] for r in due_rows]

        # All topics
        all_topics = await cypher_query(conn, GRAPH_NAME, "MATCH (t:Topic) RETURN t")
        all_ids = set()
        for t in all_topics:
            props = t.get("properties", t) if isinstance(t, dict) else t
            all_ids.add(props.get("id", ""))

        seen = set(mastered) | set(struggling) | set(due_for_review)
        # Also add topics in SR table but not yet due
        row = await conn.execute(
            "SELECT topic_id FROM spaced_repetition WHERE learner_id = %s",
            (learner_id,),
        )
        sr_rows = await row.fetchall()
        seen.update(r[0] for r in sr_rows)

        unseen = sorted(all_ids - seen)

        return LearnerProfile(
            learner_id=learner_id,
            name=name,
            mastered=mastered,
            struggling=struggling,
            due_for_review=due_for_review,
            unseen=unseen,
        )
