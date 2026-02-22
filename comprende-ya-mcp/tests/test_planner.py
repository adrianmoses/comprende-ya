"""Pure unit tests for curriculum planner logic — no DB required."""

from mcp_server.models import (
    Activity,
    ConceptSummary,
    ConfusionPair,
    EffectiveContext,
    PlannerProgress,
    SessionPlan,
    StudiesState,
)
from mcp_server.planner import (
    ADVANCE_OUTCOME_THRESHOLD,
    SCAFFOLD_OUTCOME_THRESHOLD,
    assign_activities,
    build_session_plan,
    compute_confusion_opportunity,
    compute_decay_urgency,
    compute_readiness,
    replan,
    score_concept,
    select_context,
)


def _concept(
    cid: str = "test_concept",
    name: str = "Test Concept",
    category: str = "grammar",
    prerequisites: list[str] | None = None,
    description: str = "A test concept",
) -> ConceptSummary:
    return ConceptSummary(
        id=cid,
        name=name,
        description=description,
        cefr_level="B2",
        category=category,
        prerequisites=prerequisites or [],
    )


def _state(
    concept_id: str = "test_concept",
    mastery: float = 0.5,
    projected_mastery: float = 0.5,
    practice_count: int = 5,
    half_life_days: float = 7.0,
) -> StudiesState:
    return StudiesState(
        concept_id=concept_id,
        mastery=mastery,
        projected_mastery=projected_mastery,
        practice_count=practice_count,
        half_life_days=half_life_days,
        last_evidence_at="2025-01-01T00:00:00+00:00",
    )


class TestDecayUrgency:
    def test_unseen_concept_is_zero(self):
        assert compute_decay_urgency(0.0, 0.0, 0) == 0.0

    def test_no_drop_is_zero(self):
        assert compute_decay_urgency(0.8, 0.8, 5) == 0.0

    def test_small_drop(self):
        # drop = 0.15, urgency = 0.15/0.3 = 0.5
        result = compute_decay_urgency(0.6, 0.45, 5)
        assert abs(result - 0.5) < 0.01

    def test_large_drop_capped_at_1(self):
        result = compute_decay_urgency(0.9, 0.3, 5)
        assert result == 1.0

    def test_high_mastery_boost(self):
        # mastery >= 0.8, drop = 0.15
        unboosted = compute_decay_urgency(0.6, 0.45, 5)  # below threshold
        boosted = compute_decay_urgency(0.85, 0.7, 5)  # above threshold
        assert boosted > unboosted

    def test_projected_greater_than_mastery_is_zero(self):
        assert compute_decay_urgency(0.5, 0.6, 5) == 0.0


class TestReadiness:
    def test_no_prerequisites(self):
        assert compute_readiness([], {}) == 1.0

    def test_all_prereqs_mastered(self):
        states = {
            "prereq_a": _state("prereq_a", mastery=0.9, projected_mastery=0.85),
            "prereq_b": _state("prereq_b", mastery=0.9, projected_mastery=0.85),
        }
        assert compute_readiness(["prereq_a", "prereq_b"], states) == 1.0

    def test_one_prereq_below_progressing(self):
        states = {
            "prereq_a": _state("prereq_a", mastery=0.9, projected_mastery=0.85),
            "prereq_b": _state("prereq_b", mastery=0.2, projected_mastery=0.2),
        }
        # prereq_b below PROGRESSING_THRESHOLD (0.3) → hard gate
        assert compute_readiness(["prereq_a", "prereq_b"], states) == 0.0

    def test_unseen_prerequisite(self):
        states = {"prereq_a": _state("prereq_a", mastery=0.9, projected_mastery=0.85)}
        assert compute_readiness(["prereq_a", "prereq_b"], states) == 0.0

    def test_partial_mastery(self):
        states = {
            "prereq_a": _state("prereq_a", mastery=0.9, projected_mastery=0.85),
            "prereq_b": _state("prereq_b", mastery=0.5, projected_mastery=0.5),
        }
        # prereq_a mastered (0.85 >= 0.8), prereq_b progressing (0.5 >= 0.3 but < 0.8)
        result = compute_readiness(["prereq_a", "prereq_b"], states)
        assert result == 0.5


class TestConfusionOpportunity:
    def test_no_confusion_pairs(self):
        assert compute_confusion_opportunity("concept_a", []) == 0.0

    def test_concept_in_pair(self):
        pairs = [ConfusionPair(concept_a="concept_a", concept_b="concept_b", evidence_count=3)]
        result = compute_confusion_opportunity("concept_a", pairs)
        assert abs(result - 0.6) < 0.01  # 3/5 = 0.6

    def test_concept_not_in_pair(self):
        pairs = [ConfusionPair(concept_a="concept_x", concept_b="concept_y", evidence_count=5)]
        assert compute_confusion_opportunity("concept_a", pairs) == 0.0

    def test_saturated_at_5(self):
        pairs = [ConfusionPair(concept_a="concept_a", concept_b="concept_b", evidence_count=10)]
        assert compute_confusion_opportunity("concept_a", pairs) == 1.0

    def test_picks_max_across_pairs(self):
        pairs = [
            ConfusionPair(concept_a="concept_a", concept_b="concept_b", evidence_count=2),
            ConfusionPair(concept_a="concept_a", concept_b="concept_c", evidence_count=4),
        ]
        result = compute_confusion_opportunity("concept_a", pairs)
        assert abs(result - 0.8) < 0.01  # max(2/5, 4/5) = 0.8


class TestScoreConcept:
    def test_unseen_with_no_prereqs(self):
        concept = _concept()
        # unseen: decay=0, readiness=1.0 (no prereqs), confusion=0
        # score = 0.5*0 + 0.3*1.0 + 0.2*0 = 0.3
        score = score_concept(concept, {}, [])
        assert abs(score - 0.3) < 0.01

    def test_decaying_concept(self):
        concept = _concept(cid="decaying")
        state = _state("decaying", mastery=0.8, projected_mastery=0.5, practice_count=10)
        score = score_concept(concept, {"decaying": state}, [])
        assert score > 0.3  # higher than unseen due to decay urgency

    def test_confused_concept(self):
        concept = _concept(cid="confused")
        pairs = [ConfusionPair(concept_a="confused", concept_b="other", evidence_count=5)]
        score = score_concept(concept, {}, pairs)
        # decay=0, readiness=1.0, confusion=1.0
        # score = 0.3 + 0.2 = 0.5
        assert abs(score - 0.5) < 0.01


class TestSelectContext:
    def test_reliable_contexts(self):
        contexts = [
            EffectiveContext(context_id="good", effectiveness=0.9, sample_count=5),
            EffectiveContext(context_id="bad", effectiveness=0.3, sample_count=10),
        ]
        concept = _concept(category="grammar")
        assert select_context(concept, contexts) == "good"

    def test_unreliable_contexts_still_used(self):
        contexts = [
            EffectiveContext(context_id="only_one", effectiveness=0.7, sample_count=1),
        ]
        concept = _concept(category="grammar")
        assert select_context(concept, contexts) == "only_one"

    def test_cold_start_grammar(self):
        concept = _concept(category="grammar")
        assert select_context(concept, []) == "structured_practice"

    def test_cold_start_vocabulary(self):
        concept = _concept(category="vocabulary")
        assert select_context(concept, []) == "casual_conversation"

    def test_cold_start_unknown_category(self):
        concept = _concept(category="obscure_topic")
        assert select_context(concept, []) == "structured_practice"

    def test_prefers_reliable_over_unreliable(self):
        contexts = [
            EffectiveContext(context_id="unreliable_high", effectiveness=0.95, sample_count=1),
            EffectiveContext(context_id="reliable_lower", effectiveness=0.7, sample_count=5),
        ]
        concept = _concept()
        # Should prefer reliable (sample_count >= 3)
        assert select_context(concept, contexts) == "reliable_lower"

    def test_scoped_by_concept_id(self):
        contexts = [
            EffectiveContext(
                context_id="role_play", concept_id="vocab_1", effectiveness=0.9, sample_count=5
            ),
            EffectiveContext(
                context_id="structured_practice", concept_id="grammar_1", effectiveness=0.8, sample_count=5
            ),
        ]
        vocab = _concept(cid="vocab_1", category="vocabulary")
        grammar = _concept(cid="grammar_1", category="grammar")
        other = _concept(cid="other_1", category="grammar")

        # Each concept gets its own best context
        assert select_context(vocab, contexts) == "role_play"
        assert select_context(grammar, contexts) == "structured_practice"
        # Unscoped concept falls back to all contexts (highest effectiveness)
        assert select_context(other, contexts) == "role_play"


class TestAssignActivities:
    def test_cold_start_no_state(self):
        """New learner — all unseen, concepts with no prereqs should get conversation."""
        concepts = [
            _concept(cid="a", name="Concept A"),
            _concept(cid="b", name="Concept B"),
        ]
        activities = assign_activities(concepts, {}, [], [], 30.0)
        assert len(activities) > 0
        assert activities[0].activity_type == "conversation"

    def test_decaying_concepts_get_review(self):
        concept = _concept(cid="decay")
        state = _state("decay", mastery=0.9, projected_mastery=0.5, practice_count=10)
        activities = assign_activities([concept], {"decay": state}, [], [], 30.0)
        assert any(a.activity_type == "review" for a in activities)

    def test_confused_concepts_get_discrimination(self):
        concept = _concept(cid="conf_a")
        pairs = [ConfusionPair(concept_a="conf_a", concept_b="conf_b", evidence_count=3)]
        activities = assign_activities([concept], {}, pairs, [], 30.0)
        assert any(a.activity_type == "discrimination" for a in activities)

    def test_progressing_concepts_get_drill(self):
        concept = _concept(cid="prog")
        state = _state("prog", mastery=0.5, projected_mastery=0.5, practice_count=5)
        activities = assign_activities([concept], {"prog": state}, [], [], 30.0)
        assert any(a.activity_type == "drill" for a in activities)

    def test_duration_trimming(self):
        concepts = [_concept(cid=f"c{i}", name=f"C{i}") for i in range(20)]
        activities = assign_activities(concepts, {}, [], [], 10.0)
        total = sum(a.duration_estimate_min for a in activities)
        # Should not exceed target by more than one activity
        assert total <= 10.0 + 8.0  # max single activity is 8 min

    def test_session_order_review_first(self):
        """Review activities should come before advance/reinforce."""
        concepts = [
            _concept(cid="review_me", name="Review Me"),
            _concept(cid="advance_me", name="Advance Me"),
        ]
        states = {
            "review_me": _state(
                "review_me", mastery=0.9, projected_mastery=0.5, practice_count=10
            ),
        }
        activities = assign_activities(concepts, states, [], [], 30.0)
        if len(activities) >= 2:
            # Review should be first
            assert activities[0].activity_type == "review"

    def test_at_least_one_activity(self):
        """Even with tight duration, at least one activity is produced."""
        concept = _concept(cid="a")
        activities = assign_activities([concept], {}, [], [], 1.0)
        assert len(activities) >= 1

    def test_max_concepts_per_activity(self):
        """Activities should have at most 3 concepts each."""
        concepts = [_concept(cid=f"c{i}", name=f"C{i}") for i in range(6)]
        activities = assign_activities(concepts, {}, [], [], 60.0)
        for act in activities:
            assert len(act.concept_ids) <= 3


class TestBuildSessionPlan:
    def test_produces_valid_plan(self):
        concepts = [_concept(cid="a"), _concept(cid="b")]
        plan = build_session_plan("learner1", concepts, [], [], [], 30.0)
        assert plan.learner_id == "learner1"
        assert plan.duration_target_min == 30.0
        assert len(plan.session_id) > 0
        assert len(plan.created_at) > 0
        assert len(plan.activities) > 0

    def test_cold_start_plan(self):
        """New learner with no state should get a valid plan."""
        concepts = [
            _concept(cid=f"c{i}", name=f"Concept {i}") for i in range(5)
        ]
        plan = build_session_plan("new_learner", concepts, [], [], [], 30.0)
        assert len(plan.activities) > 0
        # All should be conversation (unseen, no prereqs)
        for act in plan.activities:
            assert act.activity_type == "conversation"


class TestReplan:
    def _make_plan(self, activities: list[Activity]) -> SessionPlan:
        return SessionPlan(
            learner_id="test",
            session_id="test-session",
            duration_target_min=30.0,
            activities=activities,
            created_at="2025-01-01T00:00:00+00:00",
        )

    def _activity(self, activity_type: str = "conversation") -> Activity:
        return Activity(
            concept_ids=["concept_a"],
            concept_names=["Present Subjunctive"],
            activity_type=activity_type,
            context="test_context",
            instructions="Test instructions",
            duration_estimate_min=8.0,
        )

    def test_too_early(self):
        plan = self._make_plan([self._activity()])
        progress = PlannerProgress(activity_index=0, outcome_so_far=0.9, time_elapsed_min=1.0)
        result = replan(plan, progress)
        assert result.action == "continue"
        assert "Too early" in result.reason

    def test_advance_on_high_outcome(self):
        plan = self._make_plan([self._activity(), self._activity("drill")])
        progress = PlannerProgress(
            activity_index=0,
            outcome_so_far=ADVANCE_OUTCOME_THRESHOLD,
            time_elapsed_min=5.0,
        )
        result = replan(plan, progress)
        assert result.action == "advance"
        assert len(result.updated_activities) == 1  # first activity removed

    def test_scaffold_conversation_to_drill(self):
        plan = self._make_plan([self._activity("conversation")])
        progress = PlannerProgress(
            activity_index=0,
            outcome_so_far=SCAFFOLD_OUTCOME_THRESHOLD,
            time_elapsed_min=5.0,
        )
        result = replan(plan, progress)
        assert result.action == "scaffold"
        assert result.updated_activities[0].activity_type == "drill"

    def test_scaffold_drill_inserts_review(self):
        plan = self._make_plan([self._activity("drill")])
        progress = PlannerProgress(
            activity_index=0,
            outcome_so_far=0.2,
            time_elapsed_min=5.0,
        )
        result = replan(plan, progress)
        assert result.action == "scaffold"
        assert len(result.updated_activities) == 2
        assert result.updated_activities[0].activity_type == "review"

    def test_continue_normal_range(self):
        plan = self._make_plan([self._activity()])
        progress = PlannerProgress(
            activity_index=0, outcome_so_far=0.5, time_elapsed_min=5.0
        )
        result = replan(plan, progress)
        assert result.action == "continue"

    def test_out_of_range_index(self):
        plan = self._make_plan([self._activity()])
        progress = PlannerProgress(
            activity_index=5, outcome_so_far=0.5, time_elapsed_min=5.0
        )
        result = replan(plan, progress)
        assert result.action == "continue"

    def test_scaffold_uses_concept_names_not_ids(self):
        plan = self._make_plan([self._activity("conversation")])
        progress = PlannerProgress(
            activity_index=0, outcome_so_far=0.2, time_elapsed_min=5.0
        )
        result = replan(plan, progress)
        assert result.action == "scaffold"
        instructions = result.updated_activities[0].instructions
        assert "Present Subjunctive" in instructions
        assert "concept_a" not in instructions

    def test_scaffold_review_preserves_concept_names(self):
        plan = self._make_plan([self._activity("drill")])
        progress = PlannerProgress(
            activity_index=0, outcome_so_far=0.2, time_elapsed_min=5.0
        )
        result = replan(plan, progress)
        assert result.action == "scaffold"
        review = result.updated_activities[0]
        assert review.concept_names == ["Present Subjunctive"]
        assert "Present Subjunctive" in review.instructions
