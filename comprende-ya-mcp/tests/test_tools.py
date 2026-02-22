"""Integration tests for MCP tools — requires running AGE instance."""

import pytest

from mcp_server.assessment import _get_recent_concepts
from mcp_server.models import EvidenceEvent
from mcp_server.tools.concepts import query_concepts, query_concepts_batch
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


class TestQueryConceptsBatch:
    async def test_returns_requested_concepts(self, seeded_pool):
        ids = ["subjunctive_desire", "passive_se"]
        concepts = await query_concepts_batch(seeded_pool, ids)
        returned_ids = {c.id for c in concepts}
        assert returned_ids == set(ids)

    async def test_empty_list_returns_empty(self, seeded_pool):
        concepts = await query_concepts_batch(seeded_pool, [])
        assert concepts == []

    async def test_unknown_ids_ignored(self, seeded_pool):
        concepts = await query_concepts_batch(
            seeded_pool, ["nonexistent_concept", "also_fake"]
        )
        assert concepts == []

    async def test_mixed_known_and_unknown(self, seeded_pool):
        concepts = await query_concepts_batch(
            seeded_pool, ["subjunctive_desire", "nonexistent"]
        )
        assert len(concepts) == 1
        assert concepts[0].id == "subjunctive_desire"

    async def test_includes_edges(self, seeded_pool):
        concepts = await query_concepts_batch(seeded_pool, ["passive_se"])
        assert len(concepts) == 1
        c = concepts[0]
        assert "impersonal_se" in c.contrasts_with

    async def test_includes_prerequisites(self, seeded_pool):
        concepts = await query_concepts_batch(seeded_pool, ["subjunctive_desire"])
        assert len(concepts) == 1
        assert "subjunctive_present_forms" in concepts[0].prerequisites

    async def test_includes_related(self, seeded_pool):
        concepts = await query_concepts_batch(
            seeded_pool, ["subjunctive_present_forms"]
        )
        assert len(concepts) == 1
        assert "subjunctive_imperfect_forms" in concepts[0].related

    async def test_matches_single_query(self, seeded_pool):
        """Batch results should match individual query_concepts results."""
        single = await query_concepts(seeded_pool, concept_id="subjunctive_desire")
        batch = await query_concepts_batch(seeded_pool, ["subjunctive_desire"])
        assert len(single) == 1
        assert len(batch) == 1
        assert single[0].id == batch[0].id
        assert single[0].name == batch[0].name
        assert single[0].prerequisites == batch[0].prerequisites
        assert single[0].mastery_signals == batch[0].mastery_signals
        assert set(single[0].contrasts_with) == set(batch[0].contrasts_with)
        assert set(single[0].related) == set(batch[0].related)


class TestGetRecentConcepts:
    async def test_empty_for_new_learner(self, seeded_pool, clean_learner):
        concepts = await _get_recent_concepts(seeded_pool, clean_learner)
        assert concepts == []

    async def test_returns_studied_concepts(self, seeded_pool, clean_learner):
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
        concepts = await _get_recent_concepts(seeded_pool, clean_learner)
        returned_ids = {c.id for c in concepts}
        assert "subjunctive_present_forms" in returned_ids
        assert "passive_se" in returned_ids

    async def test_respects_limit(self, seeded_pool, clean_learner):
        # Ingest evidence for 3 concepts
        for cid in ["subjunctive_present_forms", "passive_se", "impersonal_se"]:
            await ingest_evidence(
                seeded_pool,
                clean_learner,
                [
                    EvidenceEvent(
                        concept_id=cid,
                        signal="produced_correctly",
                        outcome=0.8,
                    )
                ],
            )
        concepts = await _get_recent_concepts(seeded_pool, clean_learner, limit=2)
        assert len(concepts) == 2

    async def test_returns_full_concept_data(self, seeded_pool, clean_learner):
        await ingest_evidence(
            seeded_pool,
            clean_learner,
            [
                EvidenceEvent(
                    concept_id="passive_se",
                    signal="produced_correctly",
                    outcome=0.8,
                )
            ],
        )
        concepts = await _get_recent_concepts(seeded_pool, clean_learner)
        assert len(concepts) == 1
        c = concepts[0]
        # Should have full ConceptSummary data, not just IDs
        assert c.id == "passive_se"
        assert c.name != ""
        assert len(c.mastery_signals) > 0
        assert "impersonal_se" in c.contrasts_with


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
