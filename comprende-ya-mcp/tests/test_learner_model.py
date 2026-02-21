"""Pure unit tests for learner model logic — no DB required."""

from mcp_server.learner_model import (
    compute_confidence,
    compute_decayed_mastery,
    compute_propagation,
    compute_trend,
    detect_confusions,
    recompute_studies,
)


class TestDecayedMastery:
    def test_no_elapsed_time(self):
        assert compute_decayed_mastery(0.8, 1.0, 0.0) == 0.8

    def test_one_half_life(self):
        result = compute_decayed_mastery(1.0, 1.0, 1.0)
        assert abs(result - 0.5) < 1e-6

    def test_two_half_lives(self):
        result = compute_decayed_mastery(1.0, 1.0, 2.0)
        assert abs(result - 0.25) < 1e-6

    def test_longer_half_life_decays_slower(self):
        fast = compute_decayed_mastery(1.0, 1.0, 1.0)
        slow = compute_decayed_mastery(1.0, 10.0, 1.0)
        assert slow > fast

    def test_negative_elapsed_returns_unchanged(self):
        assert compute_decayed_mastery(0.8, 1.0, -1.0) == 0.8


class TestRecomputeStudies:
    def test_first_success(self):
        result = recompute_studies(
            mastery=0.0,
            half_life_days=1.0,
            practice_count=0,
            outcome=0.8,
            elapsed_days=0.0,
        )
        assert result["mastery"] > 0.0
        assert result["half_life_days"] == 2.0  # doubled on success
        assert result["practice_count"] == 1

    def test_first_failure(self):
        result = recompute_studies(
            mastery=0.0,
            half_life_days=1.0,
            practice_count=0,
            outcome=0.2,
            elapsed_days=0.0,
        )
        assert result["mastery"] > 0.0  # 0.3 * 0.2 = 0.06
        assert result["half_life_days"] == 0.5  # halved on failure
        assert result["practice_count"] == 1

    def test_success_after_decay(self):
        # Start at mastery=1.0, wait one half-life, then succeed
        result = recompute_studies(
            mastery=1.0,
            half_life_days=1.0,
            practice_count=5,
            outcome=0.8,
            elapsed_days=1.0,
        )
        # decayed = 0.5, new = 0.3*0.8 + 0.7*0.5 = 0.24 + 0.35 = 0.59
        assert abs(result["mastery"] - 0.59) < 0.01

    def test_half_life_capped_at_max(self):
        result = recompute_studies(
            mastery=0.9,
            half_life_days=80.0,
            practice_count=100,
            outcome=1.0,
            elapsed_days=0.1,
        )
        assert result["half_life_days"] == 90.0

    def test_half_life_floored_at_min(self):
        result = recompute_studies(
            mastery=0.1,
            half_life_days=0.6,
            practice_count=1,
            outcome=0.1,
            elapsed_days=0.1,
        )
        assert result["half_life_days"] == 0.5

    def test_mastery_clamped_0_to_1(self):
        result = recompute_studies(
            mastery=0.99,
            half_life_days=90.0,
            practice_count=50,
            outcome=1.0,
            elapsed_days=0.0,
        )
        assert result["mastery"] <= 1.0

    def test_ema_smoothing(self):
        # With no decay (elapsed=0), new_mastery = 0.3*outcome + 0.7*mastery
        result = recompute_studies(
            mastery=0.5,
            half_life_days=10.0,
            practice_count=3,
            outcome=1.0,
            elapsed_days=0.0,
        )
        expected = 0.3 * 1.0 + 0.7 * 0.5  # = 0.65
        assert abs(result["mastery"] - expected) < 0.001


class TestComputeTrend:
    def test_single_outcome_is_plateau(self):
        assert compute_trend([0.5]) == "plateau"

    def test_rising_outcomes(self):
        assert compute_trend([0.2, 0.4, 0.6, 0.8, 1.0]) == "rising"

    def test_declining_outcomes(self):
        assert compute_trend([1.0, 0.8, 0.6, 0.4, 0.2]) == "declining"

    def test_flat_outcomes(self):
        assert compute_trend([0.5, 0.5, 0.5, 0.5, 0.5]) == "plateau"

    def test_only_uses_last_5(self):
        # First 5 declining, last 5 rising
        outcomes = [1.0, 0.8, 0.6, 0.4, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0]
        assert compute_trend(outcomes) == "rising"

    def test_empty_is_plateau(self):
        assert compute_trend([]) == "plateau"


class TestComputeConfidence:
    def test_zero_practice(self):
        assert compute_confidence(0, []) == 0.0

    def test_one_practice(self):
        result = compute_confidence(1, [0.8])
        assert 0.0 < result < 1.0

    def test_increases_with_practice(self):
        low = compute_confidence(2, [0.8, 0.8])
        high = compute_confidence(10, [0.8] * 10)
        assert high > low

    def test_consistent_outcomes_higher_confidence(self):
        consistent = compute_confidence(5, [0.8, 0.8, 0.8, 0.8, 0.8])
        inconsistent = compute_confidence(5, [0.0, 1.0, 0.0, 1.0, 0.0])
        assert consistent > inconsistent


class TestDetectConfusions:
    def test_no_confusion_on_success(self):
        pairs = detect_confusions(
            "ser_estar",
            0.8,
            ["ser_estar_adj"],
            {"ser_estar": 3, "ser_estar_adj": 3},
        )
        assert pairs == []

    def test_no_confusion_without_enough_failures(self):
        pairs = detect_confusions(
            "ser_estar",
            0.1,
            ["ser_estar_adj"],
            {"ser_estar": 0, "ser_estar_adj": 3},
        )
        assert pairs == []

    def test_detects_confusion_pair(self):
        pairs = detect_confusions(
            "ser_estar",
            0.1,
            ["ser_estar_adj"],
            {"ser_estar": 1, "ser_estar_adj": 2},
        )
        # ser_estar now has 1+1=2 failures, ser_estar_adj has 2
        assert len(pairs) == 1
        a, b = pairs[0]
        assert a < b  # sorted order

    def test_no_confusion_if_partner_below_threshold(self):
        pairs = detect_confusions(
            "ser_estar",
            0.1,
            ["ser_estar_adj"],
            {"ser_estar": 1, "ser_estar_adj": 1},
        )
        assert pairs == []

    def test_multiple_contrast_partners(self):
        pairs = detect_confusions(
            "passive_se",
            0.1,
            ["impersonal_se", "reflexive_verbs"],
            {"passive_se": 2, "impersonal_se": 3, "reflexive_verbs": 2},
        )
        # passive_se has 2+1=3, impersonal_se has 3, reflexive_verbs has 2
        assert len(pairs) == 2


class TestComputePropagation:
    def test_no_propagation_below_threshold(self):
        boosts = compute_propagation(0.05, [("related_concept", 0.5)])
        assert boosts == []

    def test_propagation_above_threshold(self):
        boosts = compute_propagation(0.2, [("related_concept", 0.5)])
        assert len(boosts) == 1
        cid, boost = boosts[0]
        assert cid == "related_concept"
        # 0.2 * 0.5 * 0.2 = 0.02
        assert abs(boost - 0.02) < 0.001

    def test_propagation_proportional_to_strength(self):
        boosts = compute_propagation(0.3, [("strong", 1.0), ("weak", 0.2)])
        assert len(boosts) == 2
        strong_boost = next(b for c, b in boosts if c == "strong")
        weak_boost = next(b for c, b in boosts if c == "weak")
        assert strong_boost > weak_boost

    def test_no_propagation_if_no_related(self):
        boosts = compute_propagation(0.5, [])
        assert boosts == []
