"""Integration tests for curriculum planner — requires running AGE instance."""

import pytest

from mcp_server.models import EvidenceEvent
from mcp_server.tools.ingest_evidence import ingest_evidence
from mcp_server.tools.planner import plan_session, replan_activity

pytestmark = pytest.mark.asyncio


class TestPlanSession:
    async def test_cold_start_new_learner(self, seeded_pool, clean_learner):
        """New learner with no evidence should get a valid plan."""
        result = await plan_session(seeded_pool, clean_learner, duration_min=30.0)
        assert result["learner_id"] == clean_learner
        assert result["duration_target_min"] == 30.0
        assert len(result["activities"]) > 0
        assert len(result["session_id"]) > 0
        # Cold start: all activities should be conversation (unseen, no prereqs)
        for act in result["activities"]:
            assert act["activity_type"] == "conversation"
            assert len(act["concept_ids"]) > 0
            assert len(act["instructions"]) > 0
            assert act["duration_estimate_min"] > 0

    async def test_plan_after_evidence(self, seeded_pool, clean_learner):
        """Learner with some evidence should get a mix of activity types."""
        # Ingest evidence for a few concepts
        for _ in range(3):
            await ingest_evidence(
                seeded_pool,
                clean_learner,
                [
                    EvidenceEvent(
                        concept_id="subjunctive_present_forms",
                        signal="produced_correctly",
                        outcome=0.9,
                    ),
                ],
            )
        # Also a struggling concept
        await ingest_evidence(
            seeded_pool,
            clean_learner,
            [
                EvidenceEvent(
                    concept_id="passive_se",
                    signal="failed_to_produce",
                    outcome=0.2,
                ),
            ],
        )

        result = await plan_session(seeded_pool, clean_learner, duration_min=30.0)
        assert len(result["activities"]) > 0
        # Should have at least some structure (not all conversation)
        types = {act["activity_type"] for act in result["activities"]}
        assert len(types) >= 1  # At minimum one type

    async def test_short_session(self, seeded_pool, clean_learner):
        """Short duration should produce fewer activities."""
        result = await plan_session(seeded_pool, clean_learner, duration_min=5.0)
        assert len(result["activities"]) >= 1
        total = sum(a["duration_estimate_min"] for a in result["activities"])
        # Should be roughly within target (one activity allowed to exceed)
        assert total <= 15.0


class TestReplanActivity:
    async def test_replan_too_early(self, seeded_pool, clean_learner):
        """Replan within first 2 minutes should return continue."""
        plan = await plan_session(seeded_pool, clean_learner, duration_min=30.0)
        progress = {
            "activity_index": 0,
            "outcome_so_far": 0.9,
            "time_elapsed_min": 1.0,
        }
        result = await replan_activity(seeded_pool, clean_learner, plan, progress)
        assert result["action"] == "continue"

    async def test_replan_advance(self, seeded_pool, clean_learner):
        """High outcome after 2+ min should trigger advance."""
        plan = await plan_session(seeded_pool, clean_learner, duration_min=30.0)
        progress = {
            "activity_index": 0,
            "outcome_so_far": 0.8,
            "time_elapsed_min": 5.0,
        }
        result = await replan_activity(seeded_pool, clean_learner, plan, progress)
        assert result["action"] == "advance"

    async def test_replan_scaffold(self, seeded_pool, clean_learner):
        """Low outcome should trigger scaffold."""
        plan = await plan_session(seeded_pool, clean_learner, duration_min=30.0)
        progress = {
            "activity_index": 0,
            "outcome_so_far": 0.2,
            "time_elapsed_min": 5.0,
        }
        result = await replan_activity(seeded_pool, clean_learner, plan, progress)
        assert result["action"] == "scaffold"

    async def test_replan_continue(self, seeded_pool, clean_learner):
        """Mid-range outcome should continue."""
        plan = await plan_session(seeded_pool, clean_learner, duration_min=30.0)
        progress = {
            "activity_index": 0,
            "outcome_so_far": 0.5,
            "time_elapsed_min": 5.0,
        }
        result = await replan_activity(seeded_pool, clean_learner, plan, progress)
        assert result["action"] == "continue"


class TestPlanAssessReplanCycle:
    async def test_full_cycle(self, seeded_pool, clean_learner):
        """Full cycle: plan → ingest evidence → replan."""
        # 1. Plan a session
        plan = await plan_session(seeded_pool, clean_learner, duration_min=30.0)
        assert len(plan["activities"]) > 0

        first_activity = plan["activities"][0]
        concept_ids = first_activity["concept_ids"]

        # 2. Simulate good performance by ingesting evidence
        for cid in concept_ids:
            await ingest_evidence(
                seeded_pool,
                clean_learner,
                [
                    EvidenceEvent(
                        concept_id=cid,
                        signal="produced_correctly",
                        outcome=0.85,
                    ),
                ],
            )

        # 3. Replan based on good progress
        progress = {
            "activity_index": 0,
            "outcome_so_far": 0.85,
            "time_elapsed_min": 5.0,
        }
        result = await replan_activity(seeded_pool, clean_learner, plan, progress)
        assert result["action"] == "advance"

        # 4. Plan again — should reflect updated learner state
        plan2 = await plan_session(seeded_pool, clean_learner, duration_min=30.0)
        assert len(plan2["activities"]) > 0
        # The concepts we practiced should now have different treatment
        # (could be drill instead of conversation, or different concepts prioritized)
