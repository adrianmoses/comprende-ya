"""query_concepts tool — browse the concept graph."""

from __future__ import annotations

import json
from collections import defaultdict

from mcp_server.db import cypher_query, escape_cypher
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.models import ConceptSummary


def _extract_props(row):
    if isinstance(row, dict):
        return row.get("properties", row)
    return row


def _parse_json_field(value: str | list | None) -> list[str]:
    """Parse a JSON-encoded list stored as a string property."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


async def query_concepts(
    pool,
    cefr_level: str | None = None,
    category: str | None = None,
    concept_id: str | None = None,
) -> list[ConceptSummary]:
    """Query concept nodes with optional filters.

    Args:
        pool: Database connection pool.
        cefr_level: Filter by CEFR level (e.g. "B2"). Matches if level is contained in the concept's cefr_level string.
        category: Filter by category (e.g. "grammar").
        concept_id: Return a single concept by id.
    """
    async with pool.connection() as conn:
        # Build WHERE clause
        conditions = []
        if concept_id:
            conditions.append(f"c.id = '{concept_id}'")
        if category:
            conditions.append(f"c.category = '{category}'")
        # cefr_level filtering done in Python (AGE Cypher CONTAINS is unreliable)

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        concepts = await cypher_query(
            conn, GRAPH_NAME, f"MATCH (c:Concept){where} RETURN c"
        )

        # Build concept map
        concept_map: dict[str, dict] = {}
        for c in concepts:
            props = _extract_props(c)
            cid = props.get("id", "")
            concept_map[cid] = props

        if not concept_map:
            return []

        # Filter by cefr_level in Python
        if cefr_level:
            concept_map = {
                cid: props
                for cid, props in concept_map.items()
                if cefr_level in props.get("cefr_level", "")
            }

        if not concept_map:
            return []

        # Batch-fetch REQUIRES edges
        prereqs_by_concept: dict[str, list[str]] = defaultdict(list)
        prereq_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            "MATCH (c:Concept)-[:REQUIRES]->(p:Concept) RETURN c.id, p.id",
            columns=["cid", "pid"],
        )
        for cid_val, pid_val in prereq_rows:
            prereqs_by_concept[cid_val].append(pid_val)

        # Batch-fetch RELATED_TO edges (both directions)
        related_by_concept: dict[str, list[str]] = defaultdict(list)
        related_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            "MATCH (a:Concept)-[:RELATED_TO]-(b:Concept) RETURN a.id, b.id",
            columns=["aid", "bid"],
        )
        for aid_val, bid_val in related_rows:
            if bid_val not in related_by_concept[aid_val]:
                related_by_concept[aid_val].append(bid_val)

        # Batch-fetch CONTRASTS_WITH edges
        contrasts_by_concept: dict[str, list[str]] = defaultdict(list)
        contrast_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            "MATCH (a:Concept)-[:CONTRASTS_WITH]->(b:Concept) RETURN a.id, b.id",
            columns=["aid", "bid"],
        )
        for aid_val, bid_val in contrast_rows:
            contrasts_by_concept[aid_val].append(bid_val)

        return [
            ConceptSummary(
                id=cid,
                name=props.get("name", ""),
                description=props.get("description", ""),
                cefr_level=props.get("cefr_level", ""),
                category=props.get("category", ""),
                decay_rate=props.get("decay_rate", ""),
                typical_difficulty=props.get("typical_difficulty", 0.0),
                mastery_signals=_parse_json_field(props.get("mastery_signals")),
                tags=_parse_json_field(props.get("tags")),
                prerequisites=prereqs_by_concept.get(cid, []),
                related=related_by_concept.get(cid, []),
                contrasts_with=contrasts_by_concept.get(cid, []),
            )
            for cid, props in concept_map.items()
        ]


async def query_concepts_batch(
    pool,
    concept_ids: list[str],
) -> list[ConceptSummary]:
    """Fetch multiple concepts by ID in a single pass.

    Uses one Cypher query per edge type instead of N individual lookups.
    """
    if not concept_ids:
        return []

    async with pool.connection() as conn:
        # Build IN-list filters for Cypher (AGE doesn't support list parameters)
        escaped_ids = [escape_cypher(cid) for cid in concept_ids]

        def _id_filter(alias: str) -> str:
            return " OR ".join(f"{alias}.id = '{eid}'" for eid in escaped_ids)

        concepts = await cypher_query(
            conn, GRAPH_NAME, f"MATCH (c:Concept) WHERE {_id_filter('c')} RETURN c"
        )

        concept_map: dict[str, dict] = {}
        for c in concepts:
            props = _extract_props(c)
            cid = props.get("id", "")
            concept_map[cid] = props

        if not concept_map:
            return []

        # Batch-fetch REQUIRES edges (only for matched concepts)
        prereqs_by_concept: dict[str, list[str]] = defaultdict(list)
        prereq_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (c:Concept)-[:REQUIRES]->(p:Concept) "
            f"WHERE {_id_filter('c')} RETURN c.id, p.id",
            columns=["cid", "pid"],
        )
        for cid_val, pid_val in prereq_rows:
            prereqs_by_concept[cid_val].append(pid_val)

        # Batch-fetch RELATED_TO edges
        related_by_concept: dict[str, list[str]] = defaultdict(list)
        related_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (a:Concept)-[:RELATED_TO]-(b:Concept) "
            f"WHERE {_id_filter('a')} RETURN a.id, b.id",
            columns=["aid", "bid"],
        )
        for aid_val, bid_val in related_rows:
            if bid_val not in related_by_concept[aid_val]:
                related_by_concept[aid_val].append(bid_val)

        # Batch-fetch CONTRASTS_WITH edges
        contrasts_by_concept: dict[str, list[str]] = defaultdict(list)
        contrast_rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (a:Concept)-[:CONTRASTS_WITH]->(b:Concept) "
            f"WHERE {_id_filter('a')} RETURN a.id, b.id",
            columns=["aid", "bid"],
        )
        for aid_val, bid_val in contrast_rows:
            contrasts_by_concept[aid_val].append(bid_val)

        return [
            ConceptSummary(
                id=cid,
                name=props.get("name", ""),
                description=props.get("description", ""),
                cefr_level=props.get("cefr_level", ""),
                category=props.get("category", ""),
                decay_rate=props.get("decay_rate", ""),
                typical_difficulty=props.get("typical_difficulty", 0.0),
                mastery_signals=_parse_json_field(props.get("mastery_signals")),
                tags=_parse_json_field(props.get("tags")),
                prerequisites=prereqs_by_concept.get(cid, []),
                related=related_by_concept.get(cid, []),
                contrasts_with=contrasts_by_concept.get(cid, []),
            )
            for cid, props in concept_map.items()
        ]
