"""Tests for SessionManager — mocked MCP client, no network needed."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from session_manager import BASE_PERSONA, SessionManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_PLAN: dict = {
    "learner_id": "test_learner",
    "session_id": "ses-001",
    "duration_target_min": 15.0,
    "created_at": "2025-01-01T00:00:00Z",
    "activities": [
        {
            "concept_ids": ["subjunctive_present_regular"],
            "concept_names": ["Subjuntivo presente regular"],
            "activity_type": "review",
            "context": "structured_practice",
            "instructions": "Review subjunctive present regular forms.",
            "duration_estimate_min": 5.0,
            "contrast_pair": None,
        },
        {
            "concept_ids": ["ser_vs_estar_identity"],
            "concept_names": ["Ser vs estar (identidad)"],
            "activity_type": "conversation",
            "context": "casual_conversation",
            "instructions": "Have a conversation about identity using ser/estar.",
            "duration_estimate_min": 8.0,
            "contrast_pair": None,
        },
    ],
}


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager("test_learner")


# ---------------------------------------------------------------------------
# start_structured_session — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_structured_session_returns_plan(manager: SessionManager) -> None:
    """Valid plan dict → structured mode, plan returned as-is."""
    with patch(
        "mcp_client.plan_session", new_callable=AsyncMock, return_value=FAKE_PLAN
    ):
        result = await manager.start_structured_session(duration_min=15.0)

    assert result is FAKE_PLAN
    assert manager.state is not None
    assert manager.state.mode == "structured"
    assert manager.state.session_id == "ses-001"
    assert manager.state.plan is FAKE_PLAN
    assert manager.state.current_activity_index == 0
    assert manager.state.activity_start_time is not None


@pytest.mark.asyncio
async def test_structured_session_system_prompt_includes_activity(
    manager: SessionManager,
) -> None:
    """System prompt should contain the current activity's instructions."""
    with patch(
        "mcp_client.plan_session", new_callable=AsyncMock, return_value=FAKE_PLAN
    ):
        await manager.start_structured_session()

    prompt = manager.get_system_prompt()
    assert BASE_PERSONA in prompt
    assert "review" in prompt
    assert "Subjuntivo presente regular" in prompt
    assert "Review subjunctive present regular forms." in prompt


# ---------------------------------------------------------------------------
# start_structured_session — fallback to free mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_falls_back_on_empty_dict(manager: SessionManager) -> None:
    """MCP returns {} → fall back to free mode."""
    with patch("mcp_client.plan_session", new_callable=AsyncMock, return_value={}):
        result = await manager.start_structured_session()

    assert result["mode"] == "free"
    assert manager.state is not None
    assert manager.state.mode == "free"


@pytest.mark.asyncio
async def test_falls_back_on_none(manager: SessionManager) -> None:
    """MCP returns None → fall back to free mode."""
    with patch("mcp_client.plan_session", new_callable=AsyncMock, return_value=None):
        result = await manager.start_structured_session()

    assert result["mode"] == "free"
    assert manager.state is not None
    assert manager.state.mode == "free"


@pytest.mark.asyncio
async def test_falls_back_on_non_dict(manager: SessionManager) -> None:
    """MCP returns a non-dict truthy value → fall back to free mode."""
    with patch(
        "mcp_client.plan_session",
        new_callable=AsyncMock,
        return_value="some raw string",
    ):
        result = await manager.start_structured_session()

    assert result["mode"] == "free"
    assert manager.state is not None
    assert manager.state.mode == "free"


@pytest.mark.asyncio
async def test_falls_back_on_empty_activities(manager: SessionManager) -> None:
    """MCP returns a dict with empty activities list → fall back to free mode."""
    plan_no_activities = {**FAKE_PLAN, "activities": []}
    with patch(
        "mcp_client.plan_session",
        new_callable=AsyncMock,
        return_value=plan_no_activities,
    ):
        result = await manager.start_structured_session()

    assert result["mode"] == "free"


@pytest.mark.asyncio
async def test_falls_back_on_mcp_exception(manager: SessionManager) -> None:
    """MCP call raises → plan_session returns {}, fall back to free mode."""
    with patch(
        "mcp_client.plan_session",
        new_callable=AsyncMock,
        return_value={},
    ):
        result = await manager.start_structured_session()

    assert result["mode"] == "free"


# ---------------------------------------------------------------------------
# System prompt — free mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_session_prompt_is_base_only(manager: SessionManager) -> None:
    """Free mode → system prompt is just BASE_PERSONA, no activity instructions."""
    manager.start_free_session()
    prompt = manager.get_system_prompt()
    assert prompt == BASE_PERSONA


# ---------------------------------------------------------------------------
# record_turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_turn_appends_to_buffer(manager: SessionManager) -> None:
    with patch(
        "mcp_client.plan_session", new_callable=AsyncMock, return_value=FAKE_PLAN
    ):
        await manager.start_structured_session()

    manager.record_turn("learner", "Hola profesor")
    manager.record_turn("teacher", "¡Hola! ¿Cómo estás?")

    assert manager.state is not None
    assert len(manager.state.turn_buffer) == 2
    assert manager.state.turn_buffer[0].role == "learner"
    assert manager.state.turn_buffer[1].role == "teacher"
    assert manager.state.turn_counter == 2


@pytest.mark.asyncio
async def test_record_turn_noop_without_session(manager: SessionManager) -> None:
    """record_turn does nothing when no session is active."""
    manager.record_turn("learner", "Hola")
    assert manager.state is None
