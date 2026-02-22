"""get_effective_contexts tool — query RESPONDS_WELL_TO edges for a learner."""

from __future__ import annotations

from mcp_server.db import cypher_query, escape_cypher
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.models import EffectiveContext


async def get_effective_contexts(
    pool,
    learner_id: str,
) -> list[EffectiveContext]:
    """Query RESPONDS_WELL_TO self-edges for a learner. Empty until Phase 3C."""
    lid = escape_cypher(learner_id)

    async with pool.connection() as conn:
        rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (l:Learner {{id: '{lid}'}})-[r:RESPONDS_WELL_TO]->(l) RETURN r",
        )

    contexts = []
    for r in rows:
        props = r.get("properties", r) if isinstance(r, dict) else r
        concept_id_raw = props.get("concept_id")
        contexts.append(
            EffectiveContext(
                context_id=str(props.get("context_id", "")),
                concept_id=str(concept_id_raw) if concept_id_raw else None,
                effectiveness=float(props.get("effectiveness", 0.0)),
                sample_count=int(props.get("sample_count", 0)),
            )
        )

    return contexts
