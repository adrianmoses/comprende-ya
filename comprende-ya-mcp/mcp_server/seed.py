"""Load YAML curriculum into the AGE graph.

Runnable as: uv run --package comprende-ya-mcp python -m mcp_server.seed
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import yaml

from mcp_server.db import create_pool, cypher_query
from mcp_server.graph_schema import GRAPH_NAME, init_schema

logger = logging.getLogger(__name__)

CURRICULUM_DIR = Path(__file__).parent.parent / "curriculum"


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
            escaped = json.dumps(v).replace("'", "\\'")
            parts.append(f"{k}: '{escaped}'")
    return "{" + ", ".join(parts) + "}"


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


async def seed_curriculum(yaml_path: Path | None = None) -> None:
    """Seed the curriculum from a YAML file."""
    if yaml_path is None:
        yaml_path = CURRICULUM_DIR / "a1_seed.yaml"

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    pool = await create_pool()
    try:
        await init_schema(pool)

        async with pool.connection() as conn:
            # Create topics and their content nodes
            for topic in data["topics"]:
                topic_props = {
                    "id": topic["id"],
                    "name": topic["name"],
                    "level": topic["level"],
                    "category": topic["category"],
                    "description": topic.get("description", ""),
                }
                await _create_node(conn, "Topic", topic_props)

                # Vocabulary items
                for vocab in topic.get("vocabulary", []):
                    await _create_node(conn, "Vocabulary", vocab)
                    await _create_edge(
                        conn,
                        "Topic",
                        topic["id"],
                        "CONTAINS",
                        "Vocabulary",
                        vocab["id"],
                    )

                # Grammar rules
                for rule in topic.get("grammar_rules", []):
                    await _create_node(conn, "GrammarRule", rule)
                    await _create_edge(
                        conn,
                        "Topic",
                        topic["id"],
                        "CONTAINS",
                        "GrammarRule",
                        rule["id"],
                    )

                # Phrases
                for phrase in topic.get("phrases", []):
                    await _create_node(conn, "Phrase", phrase)
                    await _create_edge(
                        conn, "Topic", topic["id"], "CONTAINS", "Phrase", phrase["id"]
                    )

            # Create prerequisite edges (REQUIRES)
            for topic in data["topics"]:
                for req_id in topic.get("requires", []):
                    await _create_edge(
                        conn, "Topic", topic["id"], "REQUIRES", "Topic", req_id
                    )

            # Create RELATED_TO edges
            for rel in data.get("relations", []):
                await _create_edge(
                    conn,
                    "Topic",
                    rel["from"],
                    "RELATED_TO",
                    "Topic",
                    rel["to"],
                    {"strength": rel.get("strength", 0.5)},
                )

        logger.info("Curriculum seeding complete")
    finally:
        await pool.close()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await seed_curriculum()


if __name__ == "__main__":
    asyncio.run(main())
