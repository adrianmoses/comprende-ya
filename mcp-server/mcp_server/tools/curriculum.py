"""query_curriculum tool — browse the curriculum graph."""

from __future__ import annotations

from collections import defaultdict

from mcp_server.db import cypher_query
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.models import TopicSummary


def _extract_props(row):
    if isinstance(row, dict):
        return row.get("properties", row)
    return row


async def query_curriculum(
    pool,
    level: str | None = None,
    category: str | None = None,
    topic_id: str | None = None,
) -> list[TopicSummary]:
    """Query curriculum topics with optional filters.

    Args:
        pool: Database connection pool.
        level: Filter by level (e.g. "A1").
        category: Filter by category (e.g. "gramatica").
        topic_id: Return a single topic by id.
    """
    async with pool.connection() as conn:
        # Build WHERE clause
        conditions = []
        if topic_id:
            conditions.append(f"t.id = '{topic_id}'")
        if level:
            conditions.append(f"t.level = '{level}'")
        if category:
            conditions.append(f"t.category = '{category}'")

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        topics = await cypher_query(
            conn, GRAPH_NAME, f"MATCH (t:Topic){where} RETURN t"
        )

        # Collect topic ids
        topic_map: dict[str, dict] = {}
        for t in topics:
            props = _extract_props(t)
            tid = props.get("id", "")
            topic_map[tid] = props

        if not topic_map:
            return []

        # Batch-fetch all CONTAINS relationships for matched topics
        # using multi-column RETURN (3 queries instead of 3*N).
        vocab_by_topic: dict[str, list[dict]] = defaultdict(list)
        grammar_by_topic: dict[str, list[dict]] = defaultdict(list)
        phrase_by_topic: dict[str, list[dict]] = defaultdict(list)

        vocab_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (t:Topic){where}-[:CONTAINS]->(v:Vocabulary) RETURN t.id, v",
            columns=["tid", "v"],
        )
        for tid_val, v in vocab_rows:
            vocab_by_topic[tid_val].append(_extract_props(v))

        grammar_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (t:Topic){where}-[:CONTAINS]->(g:GrammarRule) RETURN t.id, g",
            columns=["tid", "g"],
        )
        for tid_val, g in grammar_rows:
            grammar_by_topic[tid_val].append(_extract_props(g))

        phrase_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (t:Topic){where}-[:CONTAINS]->(p:Phrase) RETURN t.id, p",
            columns=["tid", "p"],
        )
        for tid_val, p in phrase_rows:
            phrase_by_topic[tid_val].append(_extract_props(p))

        return [
            TopicSummary(
                id=tid,
                name=props.get("name", ""),
                level=props.get("level", ""),
                category=props.get("category", ""),
                description=props.get("description", ""),
                vocabulary=vocab_by_topic.get(tid, []),
                grammar_rules=grammar_by_topic.get(tid, []),
                phrases=phrase_by_topic.get(tid, []),
            )
            for tid, props in topic_map.items()
        ]
