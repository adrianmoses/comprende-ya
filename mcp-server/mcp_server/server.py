"""FastMCP server with tool registration and lifespan DB pool management.

Run: uv run --package mcp-server python -m mcp_server.server
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import Context, FastMCP

from mcp_server.db import create_pool
from mcp_server.graph_schema import init_schema
from mcp_server.tools.curriculum import query_curriculum as _query_curriculum
from mcp_server.tools.learner import get_learner_profile as _get_learner_profile
from mcp_server.tools.next_topics import get_next_topics as _get_next_topics
from mcp_server.tools.record_attempt import record_attempt as _record_attempt
from mcp_server.tools.session_context import get_session_context as _get_session_context


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Initialize DB pool on startup, close on shutdown."""
    pool = await create_pool()
    await init_schema(pool)
    try:
        yield {"pool": pool}
    finally:
        await pool.close()


mcp = FastMCP(
    "comprende-ya-mcp",
    lifespan=lifespan,
)


def _get_pool(ctx: Context) -> Any:
    """Extract pool from lifespan context."""
    return ctx.request_context.lifespan_context["pool"]  # type: ignore[union-attr]


@mcp.tool
async def query_curriculum(
    ctx: Context,
    level: str | None = None,
    category: str | None = None,
    topic_id: str | None = None,
) -> list[dict]:
    """Browse the Spanish curriculum. Filter by level, category, or topic_id."""
    pool = _get_pool(ctx)
    topics = await _query_curriculum(
        pool, level=level, category=category, topic_id=topic_id
    )
    return [t.model_dump() for t in topics]


@mcp.tool
async def get_next_topics(
    ctx: Context,
    learner_id: str,
    limit: int = 3,
) -> list[dict]:
    """Get recommended next topics for a learner based on SR schedule and prerequisites."""
    pool = _get_pool(ctx)
    return await _get_next_topics(pool, learner_id=learner_id, limit=limit)


@mcp.tool
async def record_attempt(
    ctx: Context,
    learner_id: str,
    topic_id: str,
    result: str,
    details: str | None = None,
) -> dict:
    """Record a learning attempt (correct/incorrect) and update spaced repetition state."""
    pool = _get_pool(ctx)
    attempt = await _record_attempt(
        pool, learner_id=learner_id, topic_id=topic_id, result=result, details=details
    )
    return attempt.model_dump()


@mcp.tool
async def get_learner_profile(
    ctx: Context,
    learner_id: str,
) -> dict:
    """Get a learner's profile: mastered, struggling, due, and unseen topics."""
    pool = _get_pool(ctx)
    profile = await _get_learner_profile(pool, learner_id=learner_id)
    return profile.model_dump()


@mcp.tool
async def get_session_context(
    ctx: Context,
    session_id: str,
) -> dict:
    """Get session context for LLM prompt enrichment with curriculum content and learner summary."""
    pool = _get_pool(ctx)
    session_ctx = await _get_session_context(pool, session_id=session_id)
    return session_ctx.model_dump()


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
