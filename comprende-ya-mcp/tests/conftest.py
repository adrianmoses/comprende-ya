"""Shared fixtures for MCP server tests."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

from mcp_server.b2_seed import seed_b2_concepts
from mcp_server.db import create_pool
from mcp_server.graph_schema import GRAPH_NAME, drop_graph, init_schema

# Skip all tests if AGE_HOST is not set and not running locally
SKIP_DB = os.getenv("SKIP_DB_TESTS", "").lower() in ("1", "true", "yes")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def pool():
    """Create a test DB pool. Requires a running AGE instance."""
    if SKIP_DB:
        pytest.skip("Database tests skipped (SKIP_DB_TESTS=1)")
    p = await create_pool(min_size=1, max_size=2)
    yield p
    await p.close()


@pytest_asyncio.fixture(scope="session")
async def seeded_pool(pool):
    """Pool with schema initialized and B2 concepts seeded."""
    await drop_graph(pool)
    await init_schema(pool)
    await seed_b2_concepts(pool=pool)
    yield pool


@pytest_asyncio.fixture
async def clean_learner(pool):
    """Clean up test learner data after each test."""
    learner_id = "test_learner"
    yield learner_id
    # Cleanup: remove all dynamic edges and learner node
    async with pool.connection() as conn:
        from mcp_server.db import cypher_query

        try:
            # Remove all edges from/to learner (STUDIES, EVIDENCE, CONFUSES_WITH, RESPONDS_WELL_TO)
            await cypher_query(
                conn,
                GRAPH_NAME,
                f"MATCH (l:Learner {{id: '{learner_id}'}})-[r]-() DELETE r",
            )
            await cypher_query(
                conn,
                GRAPH_NAME,
                f"MATCH (l:Learner {{id: '{learner_id}'}}) DELETE l",
            )
        except Exception:
            pass
