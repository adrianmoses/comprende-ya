"""Pure unit tests for SM-2 spaced repetition logic."""

from datetime import datetime, timedelta, timezone

from mcp_server.spaced_repetition import SRState, is_due_for_review, update_sr


class TestUpdateSR:
    def test_first_correct_answer_sets_interval_1(self):
        state = SRState()
        new = update_sr(state, quality=4)
        assert new.interval_days == 1.0
        assert new.repetitions == 1
        assert new.ease_factor >= 2.5

    def test_second_correct_answer_sets_interval_6(self):
        state = SRState(repetitions=1, interval_days=1.0)
        new = update_sr(state, quality=4)
        assert new.interval_days == 6.0
        assert new.repetitions == 2

    def test_third_correct_uses_ease_factor(self):
        state = SRState(repetitions=2, interval_days=6.0, ease_factor=2.5)
        new = update_sr(state, quality=4)
        assert new.interval_days == 15.0  # 6.0 * 2.5
        assert new.repetitions == 3

    def test_incorrect_resets_to_1_day(self):
        state = SRState(repetitions=5, interval_days=30.0, ease_factor=2.5)
        new = update_sr(state, quality=1)
        assert new.interval_days == 1.0
        assert new.repetitions == 0

    def test_incorrect_decreases_ease_factor(self):
        state = SRState(ease_factor=2.5)
        new = update_sr(state, quality=1)
        assert new.ease_factor == 2.3

    def test_ease_factor_minimum_is_1_3(self):
        state = SRState(ease_factor=1.3)
        new = update_sr(state, quality=1)
        assert new.ease_factor == 1.3  # can't go below 1.3

    def test_perfect_score_increases_ease(self):
        state = SRState(ease_factor=2.5)
        new = update_sr(state, quality=5)
        assert new.ease_factor == 2.6

    def test_next_review_is_set(self):
        state = SRState()
        new = update_sr(state, quality=4)
        assert new.next_review is not None
        assert new.next_review > datetime.now(timezone.utc)

    def test_last_attempt_is_set(self):
        state = SRState()
        new = update_sr(state, quality=4)
        assert new.last_attempt is not None


class TestIsDueForReview:
    def test_no_review_date_means_due(self):
        state = SRState(next_review=None)
        assert is_due_for_review(state) is True

    def test_past_date_is_due(self):
        state = SRState(next_review=datetime.now(timezone.utc) - timedelta(hours=1))
        assert is_due_for_review(state) is True

    def test_future_date_is_not_due(self):
        state = SRState(next_review=datetime.now(timezone.utc) + timedelta(days=1))
        assert is_due_for_review(state) is False
