"""Thin MCP client wrapper for calling the comprende-ya MCP server."""

from __future__ import annotations

import logging
import os

from fastmcp import Client

logger = logging.getLogger(__name__)

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp")


def _get_client() -> Client:
    return Client(MCP_SERVER_URL)


async def get_next_topics(learner_id: str, limit: int = 3) -> list[dict]:
    """Fetch recommended topics for a learner."""
    try:
        async with _get_client() as client:
            result = await client.call_tool(
                "get_next_topics",
                {"learner_id": learner_id, "limit": limit},
            )
            return result
    except Exception as e:
        logger.warning("MCP call get_next_topics failed: %s", e)
        return []


async def get_session_context(session_id: str) -> dict | None:
    """Fetch session context for LLM prompt enrichment."""
    try:
        async with _get_client() as client:
            result = await client.call_tool(
                "get_session_context",
                {"session_id": session_id},
            )
            return result
    except Exception as e:
        logger.warning("MCP call get_session_context failed: %s", e)
        return None


async def record_attempt(
    learner_id: str, topic_id: str, result: str, details: str | None = None
) -> dict | None:
    """Record a learning attempt."""
    try:
        async with _get_client() as client:
            resp = await client.call_tool(
                "record_attempt",
                {
                    "learner_id": learner_id,
                    "topic_id": topic_id,
                    "result": result,
                    "details": details,
                },
            )
            return resp
    except Exception as e:
        logger.warning("MCP call record_attempt failed: %s", e)
        return None


async def get_learner_profile(learner_id: str) -> dict | None:
    """Get learner profile."""
    try:
        async with _get_client() as client:
            result = await client.call_tool(
                "get_learner_profile",
                {"learner_id": learner_id},
            )
            return result
    except Exception as e:
        logger.warning("MCP call get_learner_profile failed: %s", e)
        return None
