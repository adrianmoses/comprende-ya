"""Integration tests for graph traversal — requires running AGE instance."""

import pytest

from mcp_server.db import cypher_query
from mcp_server.graph_schema import GRAPH_NAME

pytestmark = pytest.mark.asyncio


class TestPrerequisiteChains:
    async def test_ser_estar_requires_saludos(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (t:Topic {id: 'ser_estar'})-[:REQUIRES]->(p:Topic) RETURN p",
            )
            assert len(results) == 1
            props = results[0].get("properties", results[0])
            assert props["id"] == "saludos"

    async def test_articulos_requires_saludos(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (t:Topic {id: 'articulos_genero'})-[:REQUIRES]->(p:Topic) RETURN p",
            )
            assert len(results) == 1
            props = results[0].get("properties", results[0])
            assert props["id"] == "saludos"

    async def test_saludos_has_no_prerequisites(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (t:Topic {id: 'saludos'})-[:REQUIRES]->(p:Topic) RETURN p",
            )
            assert len(results) == 0

    async def test_numeros_has_no_prerequisites(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (t:Topic {id: 'numeros'})-[:REQUIRES]->(p:Topic) RETURN p",
            )
            assert len(results) == 0


class TestContainsQueries:
    async def test_saludos_contains_vocabulary(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (t:Topic {id: 'saludos'})-[:CONTAINS]->(v:Vocabulary) RETURN v",
            )
            assert len(results) == 3
            ids = {r.get("properties", r).get("id") for r in results}
            assert "vocab_hola" in ids
            assert "vocab_nombre" in ids
            assert "vocab_bien" in ids

    async def test_saludos_contains_phrases(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (t:Topic {id: 'saludos'})-[:CONTAINS]->(p:Phrase) RETURN p",
            )
            assert len(results) == 2

    async def test_ser_estar_contains_grammar_rules(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (t:Topic {id: 'ser_estar'})-[:CONTAINS]->(g:GrammarRule) RETURN g",
            )
            assert len(results) == 2
            ids = {r.get("properties", r).get("id") for r in results}
            assert "rule_ser" in ids
            assert "rule_estar" in ids


class TestRelatedTo:
    async def test_ser_estar_related_to_articulos(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (a:Topic {id: 'ser_estar'})-[r:RELATED_TO]->(b:Topic {id: 'articulos_genero'}) RETURN r",
            )
            assert len(results) == 1

    async def test_saludos_related_to_numeros(self, seeded_pool):
        async with seeded_pool.connection() as conn:
            results = await cypher_query(
                conn,
                GRAPH_NAME,
                "MATCH (a:Topic {id: 'saludos'})-[r:RELATED_TO]->(b:Topic {id: 'numeros'}) RETURN r",
            )
            assert len(results) == 1
