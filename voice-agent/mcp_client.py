"""Thin MCP client wrapper for calling the comprende-ya MCP server."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastmcp import Client

logger = logging.getLogger(__name__)

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp")


def _get_client() -> Client:
    return Client(MCP_SERVER_URL)


def _parse_result(result: Any) -> Any:
    """Extract usable data from MCP call_tool result.

    fastmcp returns a list of content objects; we extract the first text
    content and parse it as JSON.
    """
    if isinstance(result, (dict, list)):
        return result
    # fastmcp returns list[TextContent | ...]; grab first text block
    if isinstance(result, list) and len(result) > 0:
        first = result[0]
        text = getattr(first, "text", None)
        if text:
            return json.loads(text)
    # single TextContent
    text = getattr(result, "text", None)
    if text:
        return json.loads(text)
    return result


async def plan_session(learner_id: str, duration_min: float = 30.0) -> dict:
    """Produce a full SessionPlan for a learner."""
    try:
        async with _get_client() as client:
            result = await client.call_tool(
                "plan_session",
                {"learner_id": learner_id, "duration_min": duration_min},
            )
            return _parse_result(result)
    except Exception as e:
        logger.warning("MCP call plan_session failed: %s", e)
        return {}


async def replan_activity(learner_id: str, session_plan: dict, progress: dict) -> dict:
    """Lightweight intra-session replanning."""
    try:
        async with _get_client() as client:
            result = await client.call_tool(
                "replan_activity",
                {
                    "learner_id": learner_id,
                    "session_plan": session_plan,
                    "progress": progress,
                },
            )
            return _parse_result(result)
    except Exception as e:
        logger.warning("MCP call replan_activity failed: %s", e)
        return {}


async def assess_interaction(
    learner_id: str,
    session_id: str,
    turns: list[dict],
    target_concept_ids: list[str] | None = None,
) -> dict:
    """Assess a conversation transcript using the LLM judge."""
    try:
        async with _get_client() as client:
            args: dict[str, Any] = {
                "learner_id": learner_id,
                "session_id": session_id,
                "turns": turns,
            }
            if target_concept_ids:
                args["target_concept_ids"] = target_concept_ids
            result = await client.call_tool("assess_interaction", args)
            return _parse_result(result)
    except Exception as e:
        logger.warning("MCP call assess_interaction failed: %s", e)
        return {}


async def get_learner_profile(learner_id: str) -> dict:
    """Get learner profile (mastered/progressing/decaying/unseen)."""
    try:
        async with _get_client() as client:
            result = await client.call_tool(
                "get_learner_profile",
                {"learner_id": learner_id},
            )
            return _parse_result(result)
    except Exception as e:
        logger.warning("MCP call get_learner_profile failed: %s", e)
        return {}


async def get_learner_state(
    learner_id: str, concept_ids: list[str] | None = None
) -> list[dict]:
    """Get STUDIES state with decay projection."""
    try:
        async with _get_client() as client:
            args: dict[str, Any] = {"learner_id": learner_id}
            if concept_ids:
                args["concept_ids"] = concept_ids
            result = await client.call_tool("get_learner_state", args)
            return _parse_result(result)
    except Exception as e:
        logger.warning("MCP call get_learner_state failed: %s", e)
        return []


async def get_confusion_pairs(learner_id: str) -> list[dict]:
    """Get confusion pairs for a learner."""
    try:
        async with _get_client() as client:
            result = await client.call_tool(
                "get_confusion_pairs",
                {"learner_id": learner_id},
            )
            return _parse_result(result)
    except Exception as e:
        logger.warning("MCP call get_confusion_pairs failed: %s", e)
        return []


async def get_effective_contexts(learner_id: str) -> list[dict]:
    """Get effective learning contexts for a learner."""
    try:
        async with _get_client() as client:
            result = await client.call_tool(
                "get_effective_contexts",
                {"learner_id": learner_id},
            )
            return _parse_result(result)
    except Exception as e:
        logger.warning("MCP call get_effective_contexts failed: %s", e)
        return []


async def ingest_evidence(learner_id: str, events: list[dict]) -> dict:
    """Ingest evidence events into the learner model."""
    try:
        async with _get_client() as client:
            result = await client.call_tool(
                "ingest_evidence",
                {"learner_id": learner_id, "events": events},
            )
            return _parse_result(result)
    except Exception as e:
        logger.warning("MCP call ingest_evidence failed: %s", e)
        return {}
