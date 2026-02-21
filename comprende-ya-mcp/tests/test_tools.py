"""Integration tests for MCP tools — requires running AGE instance."""

import pytest

from mcp_server.models import EvidenceEvent
from mcp_server.tools.concepts import query_concepts
from mcp_server.tools.confusion_pairs import get_confusion_pairs
from mcp_server.tools.effective_contexts import get_effective_contexts
from mcp_server.tools.ingest_evidence import ingest_evidence
from mcp_server.tools.learner import get_learner_profile
from mcp_server.tools.learner_state import get_learner_state

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


class TestIngestEvidence:
    async def test_creates_evidence_and_studies(self, seeded_pool, clean_learner):
        result = await ingest_evidence(
            seeded_pool,
            clean_learner,
            [
                EvidenceEvent(
                    concept_id="subjunctive_present_forms",
                    signal="produced_correctly",
                    outcome=0.8,
                )
            ],
        )
        assert result["processed"] == 1
        assert len(result["studies_updated"]) == 1
        assert result["studies_updated"][0]["concept_id"] == "subjunctive_present_forms"
        assert result["studies_updated"][0]["mastery"] > 0.0

    async def test_batch_processing(self, seeded_pool, clean_learner):
        events = [
            EvidenceEvent(
                concept_id="subjunctive_present_forms",
                signal="produced_correctly",
                outcome=0.8,
            ),
            EvidenceEvent(
                concept_id="subjunctive_present_forms",
                signal="produced_correctly",
                outcome=0.9,
            ),
        ]
        result = await ingest_evidence(seeded_pool, clean_learner, events)
        assert result["processed"] == 2
        assert len(result["studies_updated"]) == 2
        # Second event should have higher mastery due to EMA
        assert (
            result["studies_updated"][1]["mastery"]
            > result["studies_updated"][0]["mastery"]
        )

    async def test_failure_shrinks_half_life(self, seeded_pool, clean_learner):
        # First success to establish baseline
        await ingest_evidence(
            seeded_pool,
            clean_learner,
            [
                EvidenceEvent(
                    concept_id="subjunctive_present_forms",
                    signal="produced_correctly",
                    outcome=0.8,
                )
            ],
        )
        # Then failure
        await ingest_evidence(
            seeded_pool,
            clean_learner,
            [
                EvidenceEvent(
                    concept_id="subjunctive_present_forms",
                    signal="failed_to_produce",
                    outcome=0.1,
                )
            ],
        )
        states = await get_learner_state(
            seeded_pool,
            clean_learner,
            concept_ids=["subjunctive_present_forms"],
        )
        assert len(states) == 1
        # After success (hl=2.0) then failure (hl=1.0)
        assert states[0].half_life_days == 1.0

    async def test_updates_studies_edge(self, seeded_pool, clean_learner):
        for _ in range(3):
            await ingest_evidence(
                seeded_pool,
                clean_learner,
                [
                    EvidenceEvent(
                        concept_id="subjunctive_present_forms",
                        signal="produced_correctly",
                        outcome=0.9,
                    )
                ],
            )
        states = await get_learner_state(
            seeded_pool,
            clean_learner,
            concept_ids=["subjunctive_present_forms"],
        )
        assert len(states) == 1
        assert states[0].practice_count == 3
        assert states[0].mastery > 0.5


class TestIngestEvidenceConfusion:
    async def test_detects_confusion_pair(self, seeded_pool, clean_learner):
        # passive_se and impersonal_se have CONTRASTS_WITH edge
        # Create enough failures on both
        for _ in range(2):
            await ingest_evidence(
                seeded_pool,
                clean_learner,
                [
                    EvidenceEvent(
                        concept_id="passive_se",
                        signal="failed_to_produce",
                        outcome=0.1,
                    )
                ],
            )
        for _ in range(2):
            await ingest_evidence(
                seeded_pool,
                clean_learner,
                [
                    EvidenceEvent(
                        concept_id="impersonal_se",
                        signal="confused_with",
                        outcome=0.1,
                    )
                ],
            )

        # Check confusion pairs
        pairs = await get_confusion_pairs(seeded_pool, clean_learner)
        pair_tuples = {(p.concept_a, p.concept_b) for p in pairs}
        assert ("impersonal_se", "passive_se") in pair_tuples or (
            "passive_se",
            "impersonal_se",
        ) in pair_tuples


class TestGetLearnerState:
    async def test_empty_for_new_learner(self, seeded_pool, clean_learner):
        states = await get_learner_state(seeded_pool, clean_learner)
        assert states == []

    async def test_returns_after_evidence(self, seeded_pool, clean_learner):
        await ingest_evidence(
            seeded_pool,
            clean_learner,
            [
                EvidenceEvent(
                    concept_id="subjunctive_present_forms",
                    signal="produced_correctly",
                    outcome=0.8,
                )
            ],
        )
        states = await get_learner_state(seeded_pool, clean_learner)
        assert len(states) == 1
        assert states[0].concept_id == "subjunctive_present_forms"
        assert states[0].mastery > 0.0
        assert states[0].practice_count == 1

    async def test_filters_by_concept_ids(self, seeded_pool, clean_learner):
        await ingest_evidence(
            seeded_pool,
            clean_learner,
            [
                EvidenceEvent(
                    concept_id="subjunctive_present_forms",
                    signal="produced_correctly",
                    outcome=0.8,
                ),
                EvidenceEvent(
                    concept_id="passive_se",
                    signal="produced_correctly",
                    outcome=0.7,
                ),
            ],
        )
        states = await get_learner_state(
            seeded_pool,
            clean_learner,
            concept_ids=["subjunctive_present_forms"],
        )
        assert len(states) == 1
        assert states[0].concept_id == "subjunctive_present_forms"


class TestGetLearnerProfile:
    async def test_new_learner_all_unseen(self, seeded_pool, clean_learner):
        profile = await get_learner_profile(seeded_pool, clean_learner)
        assert len(profile.unseen) == 53
        assert len(profile.mastered) == 0
        assert len(profile.progressing) == 0
        assert len(profile.decaying) == 0
        assert profile.total_evidence_count == 0

    async def test_after_evidence_categorizes(self, seeded_pool, clean_learner):
        # Multiple successes to build mastery
        for _ in range(5):
            await ingest_evidence(
                seeded_pool,
                clean_learner,
                [
                    EvidenceEvent(
                        concept_id="subjunctive_present_forms",
                        signal="produced_correctly",
                        outcome=0.95,
                    )
                ],
            )

        profile = await get_learner_profile(seeded_pool, clean_learner)
        # Should be mastered or progressing (depends on exact EMA value)
        assert "subjunctive_present_forms" not in profile.unseen
        assert profile.total_evidence_count == 5

    async def test_includes_confusion_pairs(self, seeded_pool, clean_learner):
        # Build up confusion between passive_se and impersonal_se
        for _ in range(2):
            await ingest_evidence(
                seeded_pool,
                clean_learner,
                [
                    EvidenceEvent(
                        concept_id="passive_se",
                        signal="failed_to_produce",
                        outcome=0.1,
                    )
                ],
            )
        for _ in range(2):
            await ingest_evidence(
                seeded_pool,
                clean_learner,
                [
                    EvidenceEvent(
                        concept_id="impersonal_se",
                        signal="confused_with",
                        outcome=0.1,
                    )
                ],
            )

        profile = await get_learner_profile(seeded_pool, clean_learner)
        assert len(profile.confusion_pairs) > 0


class TestGetConfusionPairs:
    async def test_empty_for_new_learner(self, seeded_pool, clean_learner):
        pairs = await get_confusion_pairs(seeded_pool, clean_learner)
        assert pairs == []


class TestGetEffectiveContexts:
    async def test_empty_for_new_learner(self, seeded_pool, clean_learner):
        contexts = await get_effective_contexts(seeded_pool, clean_learner)
        assert contexts == []

    async def test_tracks_context(self, seeded_pool, clean_learner):
        await ingest_evidence(
            seeded_pool,
            clean_learner,
            [
                EvidenceEvent(
                    concept_id="subjunctive_present_forms",
                    signal="produced_correctly",
                    outcome=0.9,
                    context_id="dialogue_practice",
                )
            ],
        )
        contexts = await get_effective_contexts(seeded_pool, clean_learner)
        assert len(contexts) == 1
        assert contexts[0].context_id == "dialogue_practice"
        assert contexts[0].effectiveness == 0.9
        assert contexts[0].sample_count == 1
