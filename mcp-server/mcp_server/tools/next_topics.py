"""get_next_topics tool — recommend topics based on SR schedule and prerequisites."""

from __future__ import annotations

from collections import defaultdict

from mcp_server.db import cypher_query
from mcp_server.graph_schema import GRAPH_NAME


def _extract_props(row):
    if isinstance(row, dict):
        return row.get("properties", row)
    return row


async def get_next_topics(
    pool,
    learner_id: str,
    limit: int = 3,
) -> list[dict]:
    """Return recommended topics for a learner.

    Priority:
    1. Topics due for review (from spaced_repetition table)
    2. Unseen topics whose prerequisites are all mastered
    """
    async with pool.connection() as conn:
        results = []

        # 1. Due for review
        row = await conn.execute(
            """
            SELECT topic_id, next_review, interval_days, ease_factor
            FROM spaced_repetition
            WHERE learner_id = %s AND next_review <= now()
            ORDER BY next_review ASC
            LIMIT %s
            """,
            (learner_id, limit),
        )
        due_rows = await row.fetchall()
        due_topic_ids = [dr[0] for dr in due_rows]

        # Batch-fetch topic details for all due topics
        if due_topic_ids:
            all_due_topics = await cypher_query(
                conn, GRAPH_NAME, "MATCH (t:Topic) RETURN t"
            )
            topic_name_map = {}
            for t in all_due_topics:
                props = _extract_props(t)
                topic_name_map[props.get("id", "")] = props.get("name", "")

            for dr in due_rows:
                tid = dr[0]
                results.append(
                    {
                        "topic_id": tid,
                        "name": topic_name_map.get(tid, ""),
                        "reason": "due_for_review",
                        "next_review": str(dr[1]),
                    }
                )

        if len(results) >= limit:
            return results[:limit]

        # 2. Unseen topics with satisfied prerequisites
        # Get all topic ids the learner has encountered
        row = await conn.execute(
            "SELECT topic_id FROM spaced_repetition WHERE learner_id = %s",
            (learner_id,),
        )
        seen_rows = await row.fetchall()
        seen_ids = {r[0] for r in seen_rows}

        # Get all topics and all prerequisite edges in two queries (not N)
        all_topics = await cypher_query(conn, GRAPH_NAME, "MATCH (t:Topic) RETURN t")

        prereq_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            "MATCH (t:Topic)-[:REQUIRES]->(p:Topic) RETURN t.id, p.id",
            columns=["tid", "pid"],
        )
        prereqs_by_topic: dict[str, list[str]] = defaultdict(list)
        for tid_val, pid_val in prereq_rows:
            prereqs_by_topic[tid_val].append(pid_val)

        # Get mastered topic ids (repetitions > 0 in SR table)
        row = await conn.execute(
            "SELECT topic_id FROM spaced_repetition "
            "WHERE learner_id = %s AND repetitions > 0",
            (learner_id,),
        )
        mastered_rows = await row.fetchall()
        mastered_ids = {r[0] for r in mastered_rows}

        for t in all_topics:
            if len(results) >= limit:
                break
            props = _extract_props(t)
            tid = props.get("id", "")
            if tid in seen_ids:
                continue

            # All prereqs must be mastered
            prereq_ids = prereqs_by_topic.get(tid, [])
            if all(pid in mastered_ids for pid in prereq_ids):
                results.append(
                    {
                        "topic_id": tid,
                        "name": props.get("name", ""),
                        "reason": "new_topic",
                    }
                )

        return results[:limit]
