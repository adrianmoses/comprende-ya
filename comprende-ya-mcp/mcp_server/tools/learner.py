"""get_learner_profile tool — STUDIES-based learner profile."""

from __future__ import annotations

from datetime import datetime, timezone

from mcp_server.db import cypher_query, escape_cypher
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.learner_model import (
    DECAYING_MASTERY_DROP,
    MASTERY_THRESHOLD,
    compute_decayed_mastery,
)
from mcp_server.models import ConfusionPair, LearnerProfile


async def get_learner_profile(pool, learner_id: str) -> LearnerProfile:
    """Get a learner's profile categorized by STUDIES edge state.

    Categories:
    - mastered: projected_mastery >= MASTERY_THRESHOLD
    - progressing: projected_mastery >= PROGRESSING_THRESHOLD (not mastered/decaying)
    - decaying: mastery - projected_mastery > DECAYING_MASTERY_DROP
    - unseen: no STUDIES edge
    """
    now = datetime.now(timezone.utc)
    lid = escape_cypher(learner_id)

    async with pool.connection() as conn:
        # Get all STUDIES edges
        studies_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (l:Learner {{id: '{lid}'}})"
            f"-[r:STUDIES]->"
            f"(c:Concept) RETURN r, c.id",
            columns=["r", "cid"],
        )

        # Get all concept ids
        all_rows = await cypher_query(conn, GRAPH_NAME, "MATCH (c:Concept) RETURN c.id")
        all_ids = {r if isinstance(r, str) else str(r) for r in all_rows}

        # Count total evidence
        evidence_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (l:Learner {{id: '{lid}'}})-[e:EVIDENCE]->() RETURN e",
        )
        total_evidence = len(evidence_rows)

        # Get confusion pairs
        confusion_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (l:Learner {{id: '{lid}'}})-[r:CONFUSES_WITH]->(l) RETURN r",
        )

    mastered = []
    progressing = []
    decaying = []
    seen_ids = set()

    for edge, cid in studies_rows:
        seen_ids.add(cid)
        props = edge.get("properties", edge) if isinstance(edge, dict) else edge
        mastery = float(props.get("mastery", 0.0))
        hl = float(props.get("half_life_days", 1.0))
        last_at = props.get("last_evidence_at")

        if last_at:
            try:
                last_dt = datetime.fromisoformat(last_at)
                elapsed = max(0.0, (now - last_dt).total_seconds() / 86400.0)
            except (ValueError, TypeError):
                elapsed = 0.0
        else:
            elapsed = 0.0

        projected = compute_decayed_mastery(mastery, hl, elapsed)

        if mastery - projected > DECAYING_MASTERY_DROP:
            decaying.append(cid)
        elif projected >= MASTERY_THRESHOLD:
            mastered.append(cid)
        else:
            progressing.append(cid)

    unseen = sorted(all_ids - seen_ids)

    confusion_pairs = []
    for cr in confusion_rows:
        props = cr.get("properties", cr) if isinstance(cr, dict) else cr
        confusion_pairs.append(
            ConfusionPair(
                concept_a=str(props.get("concept_a", "")),
                concept_b=str(props.get("concept_b", "")),
                evidence_count=int(props.get("evidence_count", 0)),
                last_seen_at=props.get("last_seen_at"),
            )
        )

    return LearnerProfile(
        learner_id=learner_id,
        mastered=mastered,
        progressing=progressing,
        decaying=decaying,
        unseen=unseen,
        confusion_pairs=confusion_pairs,
        total_evidence_count=total_evidence,
    )
