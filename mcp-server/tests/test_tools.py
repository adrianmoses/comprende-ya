"""Integration tests for MCP tools — requires running AGE instance."""

import pytest

from mcp_server.tools.curriculum import query_curriculum
from mcp_server.tools.learner import get_learner_profile
from mcp_server.tools.next_topics import get_next_topics
from mcp_server.tools.record_attempt import record_attempt

pytestmark = pytest.mark.asyncio


class TestQueryCurriculum:
    async def test_returns_all_topics(self, seeded_pool):
        topics = await query_curriculum(seeded_pool)
        assert len(topics) == 4

    async def test_filter_by_level(self, seeded_pool):
        topics = await query_curriculum(seeded_pool, level="A1")
        assert len(topics) == 4  # all are A1

    async def test_filter_by_category(self, seeded_pool):
        topics = await query_curriculum(seeded_pool, category="gramatica")
        assert len(topics) == 2
        ids = {t.id for t in topics}
        assert "ser_estar" in ids
        assert "articulos_genero" in ids

    async def test_filter_by_topic_id(self, seeded_pool):
        topics = await query_curriculum(seeded_pool, topic_id="saludos")
        assert len(topics) == 1
        assert topics[0].id == "saludos"
        assert len(topics[0].vocabulary) == 3
        assert len(topics[0].phrases) == 2

    async def test_topic_has_grammar_rules(self, seeded_pool):
        topics = await query_curriculum(seeded_pool, topic_id="ser_estar")
        assert len(topics[0].grammar_rules) == 2


class TestGetNextTopics:
    async def test_new_learner_gets_topics_without_prereqs(
        self, seeded_pool, clean_learner
    ):
        topics = await get_next_topics(seeded_pool, clean_learner)
        topic_ids = {t["topic_id"] for t in topics}
        # New learner should get saludos and numeros (no prereqs)
        assert "saludos" in topic_ids or "numeros" in topic_ids
        # Should NOT get ser_estar or articulos_genero (require saludos)
        assert "ser_estar" not in topic_ids
        assert "articulos_genero" not in topic_ids

    async def test_respects_limit(self, seeded_pool, clean_learner):
        topics = await get_next_topics(seeded_pool, clean_learner, limit=1)
        assert len(topics) <= 1


class TestRecordAttempt:
    async def test_correct_attempt(self, seeded_pool, clean_learner):
        result = await record_attempt(seeded_pool, clean_learner, "saludos", "correct")
        assert result.learner_id == clean_learner
        assert result.topic_id == "saludos"
        assert result.result == "correct"
        assert result.new_interval_days == 1.0
        assert result.new_ease_factor >= 2.5

    async def test_incorrect_attempt(self, seeded_pool, clean_learner):
        result = await record_attempt(
            seeded_pool, clean_learner, "saludos", "incorrect"
        )
        assert result.result == "incorrect"
        assert result.new_interval_days == 1.0
        assert result.new_ease_factor == 2.3

    async def test_multiple_correct_increases_interval(
        self, seeded_pool, clean_learner
    ):
        await record_attempt(seeded_pool, clean_learner, "saludos", "correct")
        result = await record_attempt(seeded_pool, clean_learner, "saludos", "correct")
        assert result.new_interval_days == 6.0


class TestGetLearnerProfile:
    async def test_new_learner_all_unseen(self, seeded_pool, clean_learner):
        profile = await get_learner_profile(seeded_pool, clean_learner)
        assert len(profile.unseen) == 4
        assert len(profile.mastered) == 0
        assert len(profile.struggling) == 0

    async def test_after_attempts_profile_updates(self, seeded_pool, clean_learner):
        # Record enough correct attempts for mastery
        for _ in range(3):
            await record_attempt(seeded_pool, clean_learner, "saludos", "correct")

        profile = await get_learner_profile(seeded_pool, clean_learner)
        assert "saludos" in profile.mastered
        assert "saludos" not in profile.unseen
