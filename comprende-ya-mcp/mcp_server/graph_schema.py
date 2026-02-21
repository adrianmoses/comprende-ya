"""Initialize AGE graph schema."""

from __future__ import annotations

import logging

from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

GRAPH_NAME = "comprende_ya"

VERTEX_LABELS = [
    "Concept",
    "Context",
    "Learner",
]

EDGE_LABELS = [
    # Static concept edges
    "REQUIRES",
    "RELATED_TO",
    "CONTRASTS_WITH",
    # Dynamic learner edges
    "STUDIES",
    "EVIDENCE",
    "CONFUSES_WITH",
    "RESPONDS_WELL_TO",
]


async def init_schema(pool: AsyncConnectionPool) -> None:
    """Create AGE extension, graph, and labels."""
    async with pool.connection() as conn:
        # Enable AGE extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS age")
        await conn.execute("LOAD 'age'")
        await conn.execute('SET search_path = ag_catalog, "$user", public')

        # Create graph if not exists
        row = await conn.execute(
            "SELECT count(*) FROM ag_catalog.ag_graph WHERE name = %s",
            (GRAPH_NAME,),
        )
        result = await row.fetchone()
        count = result[0] if result else 0
        if count == 0:
            await conn.execute(f"SELECT create_graph('{GRAPH_NAME}')")
            logger.info("Created graph '%s'", GRAPH_NAME)

        # Create vertex labels
        row = await conn.execute(
            "SELECT name FROM ag_catalog.ag_label WHERE graph = ("
            "  SELECT graphid FROM ag_catalog.ag_graph WHERE name = %s"
            ") AND kind = 'v'",
            (GRAPH_NAME,),
        )
        existing_vlabels = {r[0] for r in await row.fetchall()}
        for label in VERTEX_LABELS:
            if label not in existing_vlabels:
                await conn.execute(f"SELECT create_vlabel('{GRAPH_NAME}', '{label}')")
                logger.info("Created vertex label '%s'", label)

        # Create edge labels
        row = await conn.execute(
            "SELECT name FROM ag_catalog.ag_label WHERE graph = ("
            "  SELECT graphid FROM ag_catalog.ag_graph WHERE name = %s"
            ") AND kind = 'e'",
            (GRAPH_NAME,),
        )
        existing_elabels = {r[0] for r in await row.fetchall()}
        for label in EDGE_LABELS:
            if label not in existing_elabels:
                await conn.execute(f"SELECT create_elabel('{GRAPH_NAME}', '{label}')")
                logger.info("Created edge label '%s'", label)

        logger.info("Schema initialization complete")


async def drop_graph(pool: AsyncConnectionPool) -> None:
    """Drop and recreate the graph (dev/test use)."""
    async with pool.connection() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS age")
        await conn.execute("LOAD 'age'")
        await conn.execute('SET search_path = ag_catalog, "$user", public')

        row = await conn.execute(
            "SELECT count(*) FROM ag_catalog.ag_graph WHERE name = %s",
            (GRAPH_NAME,),
        )
        result = await row.fetchone()
        count = result[0] if result else 0
        if count > 0:
            await conn.execute(f"SELECT drop_graph('{GRAPH_NAME}', true)")
            logger.info("Dropped graph '%s'", GRAPH_NAME)
