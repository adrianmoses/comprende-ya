"""Seed the B2 concept graph from concept_graph.json.

Runnable as: uv run --package comprende-ya-mcp python -m mcp_server.b2_seed
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

from mcp_server.db import create_pool, cypher_query
from mcp_server.graph_schema import GRAPH_NAME, drop_graph, init_schema

logger = logging.getLogger(__name__)

CONCEPT_GRAPH_PATH = Path(__file__).parent.parent.parent / "concept_graph.json"

# Static contrast pairs (bidirectional)
CONTRAST_PAIRS: list[tuple[str, str]] = [
    ("passive_se", "impersonal_se"),
    ("ser_estar_advanced", "passive_ser"),
    ("conditional_first", "conditional_second"),
    ("conditional_second", "conditional_third"),
    ("subjunctive_desire", "subjunctive_doubt_denial"),
    ("subjunctive_temporal_clauses", "subjunctive_purpose_clauses"),
    ("reported_speech_present", "reported_speech_past"),
    ("discourse_addition", "discourse_contrast"),
    ("discourse_cause", "discourse_consequence"),
    ("discourse_concession", "subjunctive_concessive"),
    ("perifrasis_aspectuales", "perifrasis_modales"),
    ("por_para_advanced", "ser_estar_advanced"),
]


def _props_str(props: dict) -> str:
    """Build a Cypher properties string like {key: 'value', ...}."""
    parts = []
    for k, v in props.items():
        if isinstance(v, str):
            escaped = v.replace("\\", "\\\\").replace("'", "\\'")
            parts.append(f"{k}: '{escaped}'")
        elif isinstance(v, (int, float)):
            parts.append(f"{k}: {v}")
        elif v is None:
            continue
        else:
            escaped = json.dumps(v).replace("\\", "\\\\").replace("'", "\\'")
            parts.append(f"{k}: '{escaped}'")
    return "{" + ", ".join(parts) + "}"


def load_concepts(path: Path | None = None) -> tuple[dict, list[dict]]:
    """Load concept_graph.json and return (metadata, concepts)."""
    if path is None:
        path = CONCEPT_GRAPH_PATH
    with open(path) as f:
        data = json.load(f)
    return data["metadata"], data["concepts"]


def validate_dag(concepts: list[dict]) -> None:
    """Validate that REQUIRES edges form a DAG (no cycles)."""
    concept_ids = {c["id"] for c in concepts}

    # Build adjacency list
    adj: dict[str, list[str]] = defaultdict(list)
    for c in concepts:
        for prereq in c.get("prerequisites", []):
            if prereq not in concept_ids:
                raise ValueError(
                    f"Concept '{c['id']}' has unknown prerequisite '{prereq}'"
                )
            adj[c["id"]].append(prereq)

    # DFS cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {cid: WHITE for cid in concept_ids}

    def dfs(node: str) -> None:
        color[node] = GRAY
        for neighbor in adj.get(node, []):
            if color[neighbor] == GRAY:
                raise ValueError(f"Cycle detected involving '{node}' -> '{neighbor}'")
            if color[neighbor] == WHITE:
                dfs(neighbor)
        color[node] = BLACK

    for cid in concept_ids:
        if color[cid] == WHITE:
            dfs(cid)


def validate_contrast_pairs(concepts: list[dict]) -> None:
    """Validate that all CONTRAST_PAIRS reference valid concept IDs."""
    concept_ids = {c["id"] for c in concepts}
    for a, b in CONTRAST_PAIRS:
        if a not in concept_ids:
            raise ValueError(f"Contrast pair references unknown concept '{a}'")
        if b not in concept_ids:
            raise ValueError(f"Contrast pair references unknown concept '{b}'")


async def _node_exists(conn, label: str, node_id: str) -> bool:
    """Check if a node with given id already exists."""
    results = await cypher_query(
        conn,
        GRAPH_NAME,
        f"MATCH (n:{label} {{id: '{node_id}'}}) RETURN n",
    )
    return len(results) > 0


async def _create_node(conn, label: str, props: dict) -> None:
    """Create a node if it doesn't already exist."""
    if await _node_exists(conn, label, props["id"]):
        logger.debug("Node %s:%s already exists, skipping", label, props["id"])
        return
    props_s = _props_str(props)
    await cypher_query(conn, GRAPH_NAME, f"CREATE (:{label} {props_s})")
    logger.info("Created %s: %s", label, props["id"])


async def _edge_exists(
    conn, from_label: str, from_id: str, edge_label: str, to_label: str, to_id: str
) -> bool:
    """Check if an edge already exists between two nodes."""
    results = await cypher_query(
        conn,
        GRAPH_NAME,
        f"MATCH (a:{from_label} {{id: '{from_id}'}})"
        f"-[r:{edge_label}]->"
        f"(b:{to_label} {{id: '{to_id}'}}) RETURN r",
    )
    return len(results) > 0


async def _create_edge(
    conn,
    from_label: str,
    from_id: str,
    edge_label: str,
    to_label: str,
    to_id: str,
    props: dict | None = None,
) -> None:
    """Create an edge if it doesn't already exist."""
    if await _edge_exists(conn, from_label, from_id, edge_label, to_label, to_id):
        logger.debug(
            "Edge %s->%s->%s already exists, skipping", from_id, edge_label, to_id
        )
        return
    props_s = _props_str(props) if props else ""
    query = (
        f"MATCH (a:{from_label} {{id: '{from_id}'}}), "
        f"(b:{to_label} {{id: '{to_id}'}}) "
        f"CREATE (a)-[:{edge_label} {props_s}]->(b)"
    )
    await cypher_query(conn, GRAPH_NAME, query)
    logger.info("Created edge %s -[%s]-> %s", from_id, edge_label, to_id)


async def seed_b2_concepts(
    path: Path | None = None,
    pool: AsyncConnectionPool | None = None,
) -> None:
    """Seed the B2 concept graph from concept_graph.json."""
    metadata, concepts = load_concepts(path)
    validate_dag(concepts)
    validate_contrast_pairs(concepts)

    owns_pool = pool is None
    if owns_pool:
        pool = await create_pool()
    assert pool is not None
    try:
        await drop_graph(pool)
        await init_schema(pool)

        async with pool.connection() as conn:
            # Create Concept nodes
            for c in concepts:
                node_props = {
                    "id": c["id"],
                    "name": c["label"],
                    "description": c.get("description", ""),
                    "cefr_level": ",".join(c.get("cefr_range", [])),
                    "category": c.get("layer", ""),
                    "decay_rate": c.get("decay_rate", "medium"),
                    "typical_difficulty": c.get("typical_difficulty", 0.5),
                    "mastery_signals": json.dumps(c.get("assessment_signals", [])),
                    "tags": json.dumps(c.get("tags", [])),
                }
                await _create_node(conn, "Concept", node_props)

            # Create REQUIRES edges
            for c in concepts:
                for prereq_id in c.get("prerequisites", []):
                    await _create_edge(
                        conn, "Concept", c["id"], "REQUIRES", "Concept", prereq_id
                    )

            # Create RELATED_TO edges (deduplicate: only A→B if A.id < B.id)
            concept_ids = {c["id"] for c in concepts}
            related_map: dict[str, list[str]] = {
                c["id"]: c.get("related", []) for c in concepts
            }

            created_related: set[tuple[str, str]] = set()
            for c in concepts:
                cid = c["id"]
                for rel_id in c.get("related", []):
                    if rel_id not in concept_ids:
                        logger.warning(
                            "Concept '%s' has unknown related '%s', skipping",
                            cid,
                            rel_id,
                        )
                        continue
                    pair = tuple(sorted([cid, rel_id]))
                    if pair in created_related:
                        continue
                    created_related.add(pair)

                    # Bidirectional if both reference each other
                    bidirectional = cid in related_map.get(rel_id, [])
                    strength = 0.7 if bidirectional else 0.5

                    # Always create A→B where A < B
                    a, b = pair
                    await _create_edge(
                        conn,
                        "Concept",
                        a,
                        "RELATED_TO",
                        "Concept",
                        b,
                        {"strength": strength},
                    )

            # Create CONTRASTS_WITH edges (bidirectional)
            for a, b in CONTRAST_PAIRS:
                await _create_edge(conn, "Concept", a, "CONTRASTS_WITH", "Concept", b)
                await _create_edge(conn, "Concept", b, "CONTRASTS_WITH", "Concept", a)

        logger.info("B2 concept seeding complete: %d concepts", len(concepts))
    finally:
        if owns_pool:
            await pool.close()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await seed_b2_concepts()


if __name__ == "__main__":
    asyncio.run(main())
