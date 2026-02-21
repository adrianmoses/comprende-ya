"""get_confusion_pairs tool — query CONFUSES_WITH edges for a learner."""

from __future__ import annotations

from mcp_server.db import cypher_query, escape_cypher
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.models import ConfusionPair


async def get_confusion_pairs(
    pool,
    learner_id: str,
) -> list[ConfusionPair]:
    """Query CONFUSES_WITH self-edges for a learner."""
    lid = escape_cypher(learner_id)

    async with pool.connection() as conn:
        rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (l:Learner {{id: '{lid}'}})-[r:CONFUSES_WITH]->(l) RETURN r",
        )

    pairs = []
    for r in rows:
        props = r.get("properties", r) if isinstance(r, dict) else r
        pairs.append(
            ConfusionPair(
                concept_a=str(props.get("concept_a", "")),
                concept_b=str(props.get("concept_b", "")),
                evidence_count=int(props.get("evidence_count", 0)),
                last_seen_at=props.get("last_seen_at"),
            )
        )

    return pairs
