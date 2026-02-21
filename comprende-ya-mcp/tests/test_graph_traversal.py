"""Integration tests for graph traversal — requires running AGE instance."""

import pytest

from mcp_server.db import cypher_query
from mcp_server.graph_schema import GRAPH_NAME

pytestmark = pytest.mark.asyncio


class TestPrerequisiteChains:
    async def test_subjunctive_desire_requires_present_forms(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (t:Concept {id: 'subjunctive_desire'})-[:REQUIRES]->(p:Concept) RETURN p",
            )
            assert len(results) == 1
            props = results[0].get("properties", results[0])
            assert props["id"] == "subjunctive_present_forms"

    async def test_conditional_second_requires_two_prereqs(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (t:Concept {id: 'conditional_second'})-[:REQUIRES]->(p:Concept) RETURN p",
            )
            prereq_ids = {r.get("properties", r).get("id") for r in results}
            assert prereq_ids == {
                "subjunctive_imperfect_forms",
                "conditional_simple_forms",
            }

    async def test_concepts_with_no_prerequisites_exist(self, seeded_pool):
        """Several foundational concepts have no prerequisites."""
        async with seeded_pool.connection() as conn:
            # Get all concepts
            all_concepts = await cypher_query(
                conn, GRAPH_NAME, "MATCH (c:Concept) RETURN c"
            )
            # Get concepts that have prerequisites
            with_prereqs = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (c:Concept)-[:REQUIRES]->(:Concept) RETURN DISTINCT c.id",
                columns=["cid"],
            )
            with_prereq_ids = {row[0] for row in with_prereqs}

            all_ids = set()
            for c in all_concepts:
                props = c.get("properties", c) if isinstance(c, dict) else c
                all_ids.add(props.get("id", ""))

            no_prereq = all_ids - with_prereq_ids
            # Many foundational concepts have no prereqs
            assert len(no_prereq) >= 10
            assert "subjunctive_present_forms" in no_prereq
            assert "conditional_first" in no_prereq

    async def test_dag_has_no_cycles_in_db(self, seeded_pool):
        """Verify the prerequisite graph in DB is acyclic via DFS."""
        from collections import defaultdict

        async with seeded_pool.connection() as conn:
            prereq_rows = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (a:Concept)-[:REQUIRES]->(b:Concept) RETURN a.id, b.id",
                columns=["aid", "bid"],
            )

        adj: dict[str, list[str]] = defaultdict(list)
        nodes: set[str] = set()
        for aid, bid in prereq_rows:
            adj[aid].append(bid)
            nodes.add(aid)
            nodes.add(bid)

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in nodes}

        def dfs(node: str) -> None:
            color[node] = GRAY
            for neighbor in adj.get(node, []):
                if color[neighbor] == GRAY:
                    raise AssertionError(f"Cycle: {node} -> {neighbor}")
                if color[neighbor] == WHITE:
                    dfs(neighbor)
            color[node] = BLACK

        for n in nodes:
            if color[n] == WHITE:
                dfs(n)


class TestRelatedTo:
    async def test_related_to_edges_have_strength(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (:Concept)-[r:RELATED_TO]->(:Concept) RETURN r",
            )
            assert len(results) > 0
            for r in results:
                props = r.get("properties", r) if isinstance(r, dict) else r
                assert "strength" in props, f"RELATED_TO edge missing strength: {props}"
                assert 0.0 <= props["strength"] <= 1.0


class TestContrastsWith:
    async def test_contrasts_with_edges_are_bidirectional(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            forward = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (a:Concept)-[:CONTRASTS_WITH]->(b:Concept) RETURN a.id, b.id",
                columns=["aid", "bid"],
            )
            pairs_forward = {(a, b) for a, b in forward}
            # Every A→B should have B→A
            for a, b in list(pairs_forward):
                assert (b, a) in pairs_forward, (
                    f"CONTRASTS_WITH {a}->{b} exists but {b}->{a} does not"
                )

    async def test_contrasts_with_count(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (:Concept)-[r:CONTRASTS_WITH]->(:Concept) RETURN r",
            )
            # 12 pairs × 2 directions = 24 edges
            assert len(results) == 24


class TestConceptCount:
    async def test_total_concept_count(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(conn, GRAPH_NAME, "MATCH (c:Concept) RETURN c")
            assert len(results) == 53
