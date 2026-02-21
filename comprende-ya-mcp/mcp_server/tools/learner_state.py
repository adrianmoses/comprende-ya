"""get_learner_state tool — query STUDIES edges with decay projection."""

from __future__ import annotations

from datetime import datetime, timezone

from mcp_server.db import cypher_query, escape_cypher
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.learner_model import compute_decayed_mastery
from mcp_server.models import StudiesState


async def get_learner_state(
    pool,
    learner_id: str,
    concept_ids: list[str] | None = None,
) -> list[StudiesState]:
    """Query STUDIES edges, apply decay projection, return StudiesState list."""
    now = datetime.now(timezone.utc)

    async with pool.connection() as conn:
        lid = escape_cypher(learner_id)

        if concept_ids:
            # Fetch specific concepts
            results = []
            for cid in concept_ids:
                cid_esc = escape_cypher(cid)
                rows = await cypher_query(
                    conn,
                    GRAPH_NAME,
                    f"MATCH (l:Learner {{id: '{lid}'}})"
                    f"-[r:STUDIES]->"
                    f"(c:Concept {{id: '{cid_esc}'}}) RETURN r",
                )
                if rows:
                    results.append((cid, rows[0]))
        else:
            # Fetch all STUDIES edges
            rows = await cypher_query(
                conn,
                GRAPH_NAME,
                f"MATCH (l:Learner {{id: '{lid}'}})"
                f"-[r:STUDIES]->"
                f"(c:Concept) RETURN r, c.id",
                columns=["r", "cid"],
            )
            results = [(cid, r) for r, cid in rows]

    states = []
    for cid, edge in results:
        props = edge.get("properties", edge) if isinstance(edge, dict) else edge
        mastery = float(props.get("mastery", 0.0))
        hl = float(props.get("half_life_days", 1.0))
        last_at = props.get("last_evidence_at")

        # Compute elapsed days for projection
        if last_at:
            try:
                last_dt = datetime.fromisoformat(last_at)
                elapsed = max(0.0, (now - last_dt).total_seconds() / 86400.0)
            except (ValueError, TypeError):
                elapsed = 0.0
        else:
            elapsed = 0.0

        projected = compute_decayed_mastery(mastery, hl, elapsed)

        states.append(
            StudiesState(
                concept_id=cid,
                mastery=mastery,
                projected_mastery=round(projected, 4),
                confidence=float(props.get("confidence", 0.0)),
                half_life_days=hl,
                practice_count=int(props.get("practice_count", 0)),
                last_evidence_at=last_at,
                last_outcome=float(props.get("last_outcome"))
                if props.get("last_outcome") is not None
                else None,
                trend=str(props.get("trend", "plateau")),
                first_seen_at=props.get("first_seen_at"),
            )
        )

    return states
