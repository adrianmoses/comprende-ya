"""Pure unit tests for assessment prompt building and response parsing.

No DB or LLM required — tests only the prompt construction and JSON parsing logic.
"""

from __future__ import annotations

import json

import pytest

from mcp_server.assessment import (
    VALID_SIGNALS,
    _build_system_prompt,
    _build_user_prompt,
    _extract_json,
    parse_assessment_response,
)
from mcp_server.models import ConceptSummary, InteractionTurn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_concepts() -> list[ConceptSummary]:
    return [
        ConceptSummary(
            id="subjunctive_present",
            name="Present Subjunctive",
            description="Formation and use of present subjunctive mood",
            mastery_signals=[
                "correct conjugation in noun clauses",
                "use after emotion verbs",
            ],
            contrasts_with=["indicative_present"],
        ),
        ConceptSummary(
            id="indicative_present",
            name="Present Indicative",
            description="Standard present tense conjugation",
            mastery_signals=["correct regular conjugation", "stem-changing verbs"],
            contrasts_with=["subjunctive_present"],
        ),
        ConceptSummary(
            id="ser_vs_estar",
            name="Ser vs Estar",
            description="Distinction between ser and estar",
            mastery_signals=["correct usage with adjectives", "location vs identity"],
        ),
    ]


@pytest.fixture
def sample_turns() -> list[InteractionTurn]:
    return [
        InteractionTurn(
            role="teacher",
            text="¿Cómo estás hoy?",
            turn_index=0,
            timestamp="2024-01-15T10:00:00Z",
        ),
        InteractionTurn(
            role="learner",
            text="Estoy bien, gracias. Espero que tengas un buen día.",
            turn_index=1,
            timestamp="2024-01-15T10:00:05Z",
        ),
        InteractionTurn(
            role="teacher",
            text="¡Muy bien! ¿Qué hiciste ayer?",
            turn_index=2,
            timestamp="2024-01-15T10:00:10Z",
        ),
        InteractionTurn(
            role="learner",
            text="Yo soy en la casa todo el día.",
            turn_index=3,
            timestamp="2024-01-15T10:00:15Z",
        ),
    ]


VALID_CONCEPT_IDS = {"subjunctive_present", "indicative_present", "ser_vs_estar"}


# ---------------------------------------------------------------------------
# System prompt tests
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    def test_contains_signal_vocabulary(self):
        prompt = _build_system_prompt()
        for signal in VALID_SIGNALS:
            assert signal in prompt, f"Missing signal: {signal}"

    def test_contains_outcome_scale(self):
        prompt = _build_system_prompt()
        assert "1.0" in prompt
        assert "0.0" in prompt

    def test_contains_json_format(self):
        prompt = _build_system_prompt()
        assert "context_id" in prompt
        assert "events" in prompt
        assert "concept_id" in prompt


# ---------------------------------------------------------------------------
# User prompt tests
# ---------------------------------------------------------------------------


class TestUserPrompt:
    def test_includes_concept_ids(self, sample_concepts, sample_turns):
        prompt = _build_user_prompt(sample_concepts, sample_turns)
        assert "subjunctive_present" in prompt
        assert "indicative_present" in prompt
        assert "ser_vs_estar" in prompt

    def test_includes_mastery_signals(self, sample_concepts, sample_turns):
        prompt = _build_user_prompt(sample_concepts, sample_turns)
        assert "correct conjugation in noun clauses" in prompt

    def test_includes_contrasts_with(self, sample_concepts, sample_turns):
        prompt = _build_user_prompt(sample_concepts, sample_turns)
        assert "Contrasts with:" in prompt
        assert "indicative_present" in prompt

    def test_includes_turn_labels(self, sample_concepts, sample_turns):
        prompt = _build_user_prompt(sample_concepts, sample_turns)
        assert "[Turn 0] TEACHER:" in prompt
        assert "[Turn 1] LEARNER:" in prompt

    def test_includes_turn_text(self, sample_concepts, sample_turns):
        prompt = _build_user_prompt(sample_concepts, sample_turns)
        assert "Espero que tengas" in prompt
        assert "Yo soy en la casa" in prompt


# ---------------------------------------------------------------------------
# JSON extraction tests
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_direct_json(self):
        raw = '{"context_id": "test", "events": []}'
        assert _extract_json(raw) == {"context_id": "test", "events": []}

    def test_json_in_prose(self):
        raw = 'Here is my analysis:\n{"context_id": "test", "events": []}\nEnd.'
        result = _extract_json(raw)
        assert result is not None
        assert result["context_id"] == "test"

    def test_malformed_returns_none(self):
        assert _extract_json("not json at all") is None

    def test_empty_string(self):
        assert _extract_json("") is None

    def test_multiple_json_objects_picks_first(self):
        """When prose contains multiple JSON-like fragments, extract the first valid one."""
        raw = 'prefix {"context_id": "first", "events": []} middle {"context_id": "second", "events": []}'
        result = _extract_json(raw)
        assert result is not None
        assert result["context_id"] == "first"

    def test_nested_braces_in_strings(self):
        """Braces inside JSON string values should not break extraction."""
        raw = 'Analysis: {"context_id": "test {nested}", "events": []}'
        result = _extract_json(raw)
        assert result is not None
        assert result["context_id"] == "test {nested}"

    def test_markdown_code_fence(self):
        """JSON wrapped in a markdown code block."""
        raw = '```json\n{"context_id": "test", "events": []}\n```'
        result = _extract_json(raw)
        assert result is not None
        assert result["context_id"] == "test"

    def test_json_with_nested_objects(self):
        """Deeply nested JSON should parse correctly."""
        raw = json.dumps(
            {
                "context_id": "test",
                "events": [{"concept_id": "x", "nested": {"deep": True}}],
            }
        )
        result = _extract_json(f"Here: {raw} done.")
        assert result is not None
        assert result["events"][0]["nested"]["deep"] is True

    def test_only_braces_no_valid_json(self):
        """Unbalanced or non-JSON braces should return None."""
        assert _extract_json("some { broken content") is None

    def test_escaped_quotes_in_strings(self):
        """Escaped quotes inside JSON string values."""
        raw = r'{"context_id": "he said \"hello\"", "events": []}'
        result = _extract_json(raw)
        assert result is not None
        assert "hello" in result["context_id"]

    def test_array_wrapping_extracts_inner_dict(self):
        """When a dict is wrapped in an array, extract the inner dict."""
        result = _extract_json('[{"context_id": "test"}]')
        assert result is not None
        assert result["context_id"] == "test"

    def test_bare_array_no_dict_returns_none(self):
        """A JSON array with only primitives should return None."""
        assert _extract_json("[1, 2, 3]") is None


# ---------------------------------------------------------------------------
# Response parsing tests
# ---------------------------------------------------------------------------


class TestParseAssessmentResponse:
    def test_happy_path(self, sample_turns):
        raw = json.dumps(
            {
                "context_id": "casual_chat",
                "events": [
                    {
                        "concept_id": "subjunctive_present",
                        "signal": "produced_correctly",
                        "outcome": 0.9,
                        "turn_index": 1,
                    },
                    {
                        "concept_id": "ser_vs_estar",
                        "signal": "produced_with_errors",
                        "outcome": 0.3,
                        "turn_index": 3,
                    },
                ],
            }
        )
        events, ctx, errors = parse_assessment_response(
            raw, VALID_CONCEPT_IDS, sample_turns, "session-1"
        )
        assert len(events) == 2
        assert ctx == "casual_chat"
        assert len(errors) == 0
        assert events[0].concept_id == "subjunctive_present"
        assert events[0].signal == "produced_correctly"
        assert events[0].outcome == 0.9
        assert events[0].session_id == "session-1"
        assert events[0].context_id == "casual_chat"
        assert events[0].timestamp == "2024-01-15T10:00:05Z"

    def test_json_in_prose_recovery(self, sample_turns):
        raw = (
            "Based on my analysis:\n"
            + json.dumps(
                {
                    "context_id": None,
                    "events": [
                        {
                            "concept_id": "ser_vs_estar",
                            "signal": "produced_with_errors",
                            "outcome": 0.4,
                            "turn_index": 3,
                        }
                    ],
                }
            )
            + "\nThat's my assessment."
        )
        events, ctx, errors = parse_assessment_response(
            raw, VALID_CONCEPT_IDS, sample_turns, "session-1"
        )
        assert len(events) == 1
        assert events[0].concept_id == "ser_vs_estar"

    def test_unknown_concept_id_dropped(self, sample_turns):
        raw = json.dumps(
            {
                "context_id": None,
                "events": [
                    {
                        "concept_id": "nonexistent_concept",
                        "signal": "produced_correctly",
                        "outcome": 1.0,
                        "turn_index": 1,
                    }
                ],
            }
        )
        events, ctx, errors = parse_assessment_response(
            raw, VALID_CONCEPT_IDS, sample_turns, "session-1"
        )
        assert len(events) == 0
        assert any("unknown concept_id" in e for e in errors)

    def test_unknown_signal_defaulted(self, sample_turns):
        raw = json.dumps(
            {
                "context_id": None,
                "events": [
                    {
                        "concept_id": "ser_vs_estar",
                        "signal": "invented_signal",
                        "outcome": 0.5,
                        "turn_index": 1,
                    }
                ],
            }
        )
        events, ctx, errors = parse_assessment_response(
            raw, VALID_CONCEPT_IDS, sample_turns, "session-1"
        )
        assert len(events) == 1
        assert events[0].signal == "produced_with_errors"
        assert any("unknown signal" in e for e in errors)

    def test_outcome_clamping(self, sample_turns):
        raw = json.dumps(
            {
                "context_id": None,
                "events": [
                    {
                        "concept_id": "ser_vs_estar",
                        "signal": "produced_correctly",
                        "outcome": 1.5,
                        "turn_index": 1,
                    },
                    {
                        "concept_id": "subjunctive_present",
                        "signal": "failed_to_produce",
                        "outcome": -0.3,
                        "turn_index": 3,
                    },
                ],
            }
        )
        events, ctx, errors = parse_assessment_response(
            raw, VALID_CONCEPT_IDS, sample_turns, "session-1"
        )
        assert len(events) == 2
        assert events[0].outcome == 1.0
        assert events[1].outcome == 0.0

    def test_confused_with_emits_partner_event(self, sample_turns):
        raw = json.dumps(
            {
                "context_id": None,
                "events": [
                    {
                        "concept_id": "subjunctive_present",
                        "signal": "confused_with",
                        "outcome": 0.3,
                        "turn_index": 1,
                        "confused_with_concept_id": "indicative_present",
                    }
                ],
            }
        )
        events, ctx, errors = parse_assessment_response(
            raw, VALID_CONCEPT_IDS, sample_turns, "session-1"
        )
        assert len(events) == 2
        assert events[0].concept_id == "subjunctive_present"
        assert events[0].signal == "confused_with"
        assert events[1].concept_id == "indicative_present"
        assert events[1].signal == "confused_with"

    def test_confused_with_invalid_partner_no_extra_event(self, sample_turns):
        raw = json.dumps(
            {
                "context_id": None,
                "events": [
                    {
                        "concept_id": "subjunctive_present",
                        "signal": "confused_with",
                        "outcome": 0.3,
                        "turn_index": 1,
                        "confused_with_concept_id": "nonexistent",
                    }
                ],
            }
        )
        events, ctx, errors = parse_assessment_response(
            raw, VALID_CONCEPT_IDS, sample_turns, "session-1"
        )
        assert len(events) == 1  # only the original, no partner

    def test_dedup_by_concept_and_turn_index(self, sample_turns):
        raw = json.dumps(
            {
                "context_id": None,
                "events": [
                    {
                        "concept_id": "ser_vs_estar",
                        "signal": "produced_correctly",
                        "outcome": 0.9,
                        "turn_index": 1,
                    },
                    {
                        "concept_id": "ser_vs_estar",
                        "signal": "produced_with_errors",
                        "outcome": 0.5,
                        "turn_index": 1,
                    },
                ],
            }
        )
        events, ctx, errors = parse_assessment_response(
            raw, VALID_CONCEPT_IDS, sample_turns, "session-1"
        )
        assert len(events) == 1  # second one is deduped
        assert any("duplicate" in e for e in errors)

    def test_malformed_output_returns_empty_with_errors(self, sample_turns):
        events, ctx, errors = parse_assessment_response(
            "this is not json at all",
            VALID_CONCEPT_IDS,
            sample_turns,
            "session-1",
        )
        assert len(events) == 0
        assert len(errors) > 0
        assert any("Failed to parse" in e for e in errors)

    def test_context_id_set_on_all_events(self, sample_turns):
        raw = json.dumps(
            {
                "context_id": "ordering_food",
                "events": [
                    {
                        "concept_id": "subjunctive_present",
                        "signal": "produced_correctly",
                        "outcome": 0.8,
                        "turn_index": 1,
                    },
                    {
                        "concept_id": "ser_vs_estar",
                        "signal": "recognized",
                        "outcome": 0.7,
                        "turn_index": 3,
                    },
                ],
            }
        )
        events, ctx, errors = parse_assessment_response(
            raw, VALID_CONCEPT_IDS, sample_turns, "session-1"
        )
        assert all(e.context_id == "ordering_food" for e in events)

    def test_session_id_set_on_all_events(self, sample_turns):
        raw = json.dumps(
            {
                "context_id": None,
                "events": [
                    {
                        "concept_id": "ser_vs_estar",
                        "signal": "produced_correctly",
                        "outcome": 1.0,
                        "turn_index": 1,
                    }
                ],
            }
        )
        events, ctx, errors = parse_assessment_response(
            raw, VALID_CONCEPT_IDS, sample_turns, "session-1"
        )
        assert all(e.session_id == "session-1" for e in events)

    def test_empty_events_list(self, sample_turns):
        raw = json.dumps({"context_id": "test", "events": []})
        events, ctx, errors = parse_assessment_response(
            raw, VALID_CONCEPT_IDS, sample_turns, "session-1"
        )
        assert len(events) == 0
        assert len(errors) == 0
        assert ctx == "test"
