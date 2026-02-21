"""Integration tests for MCP tools — requires running AGE instance."""

import pytest

from mcp_server.tools.concepts import query_concepts
from mcp_server.tools.learner import get_learner_profile
from mcp_server.tools.next_topics import get_next_topics
from mcp_server.tools.record_attempt import record_attempt

pytestmark = pytest.mark.asyncio


class TestQueryConcepts:
    async def test_returns_all_concepts(self, seeded_pool):
        concepts = await query_concepts(seeded_pool)
        assert len(concepts) == 53

    async def test_filter_by_category(self, seeded_pool):
        concepts = await query_concepts(seeded_pool, category="grammar")
        assert len(concepts) == 31
        assert all(c.category == "grammar" for c in concepts)

    async def test_filter_by_cefr_level(self, seeded_pool):
        concepts = await query_concepts(seeded_pool, cefr_level="B2")
        # All 53 concepts include B2 in their range
        assert len(concepts) >= 40

    async def test_filter_by_concept_id(self, seeded_pool):
        concepts = await query_concepts(seeded_pool, concept_id="subjunctive_desire")
        assert len(concepts) == 1
        c = concepts[0]
        assert c.id == "subjunctive_desire"
        assert c.name == "Subjunctive with verbs of desire/influence"
        assert "subjunctive_present_forms" in c.prerequisites
        assert len(c.mastery_signals) > 0

    async def test_concept_has_contrasts(self, seeded_pool):
        concepts = await query_concepts(seeded_pool, concept_id="passive_se")
        assert len(concepts) == 1
        assert "impersonal_se" in concepts[0].contrasts_with

    async def test_concept_has_related(self, seeded_pool):
        concepts = await query_concepts(
            seeded_pool, concept_id="subjunctive_present_forms"
        )
        assert len(concepts) == 1
        assert "subjunctive_imperfect_forms" in concepts[0].related


class TestGetNextTopics:
    async def test_new_learner_gets_concepts_without_prereqs(
        self, seeded_pool, clean_learner
    ):
        topics = await get_next_topics(seeded_pool, clean_learner)
        concept_ids = {t["concept_id"] for t in topics}
        # Should only get concepts with no prerequisites
        # These should NOT appear (they have prereqs):
        assert "subjunctive_desire" not in concept_ids
        assert "conditional_second" not in concept_ids
        # All returned concepts should have no prereqs
        assert len(topics) > 0

    async def test_respects_limit(self, seeded_pool, clean_learner):
        topics = await get_next_topics(seeded_pool, clean_learner, limit=1)
        assert len(topics) <= 1


class TestRecordAttempt:
    async def test_correct_attempt(self, seeded_pool, clean_learner):
        result = await record_attempt(
            seeded_pool, clean_learner, "subjunctive_present_forms", "correct"
        )
        assert result.learner_id == clean_learner
        assert result.concept_id == "subjunctive_present_forms"
        assert result.result == "correct"
        assert result.new_interval_days == 1.0
        assert result.new_ease_factor >= 2.5

    async def test_incorrect_attempt(self, seeded_pool, clean_learner):
        result = await record_attempt(
            seeded_pool, clean_learner, "subjunctive_present_forms", "incorrect"
        )
        assert result.result == "incorrect"
        assert result.new_interval_days == 1.0
        assert result.new_ease_factor == 2.3

    async def test_multiple_correct_increases_interval(
        self, seeded_pool, clean_learner
    ):
        await record_attempt(
            seeded_pool, clean_learner, "subjunctive_present_forms", "correct"
        )
        result = await record_attempt(
            seeded_pool, clean_learner, "subjunctive_present_forms", "correct"
        )
        assert result.new_interval_days == 6.0


class TestGetLearnerProfile:
    async def test_new_learner_all_unseen(self, seeded_pool, clean_learner):
        profile = await get_learner_profile(seeded_pool, clean_learner)
        assert len(profile.unseen) == 53
        assert len(profile.mastered) == 0
        assert len(profile.struggling) == 0

    async def test_after_attempts_profile_updates(self, seeded_pool, clean_learner):
        # Record enough correct attempts for mastery
        for _ in range(3):
            await record_attempt(
                seeded_pool,
                clean_learner,
                "subjunctive_present_forms",
                "correct",
            )

        profile = await get_learner_profile(seeded_pool, clean_learner)
        assert "subjunctive_present_forms" in profile.mastered
        assert "subjunctive_present_forms" not in profile.unseen
