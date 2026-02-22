"""FastMCP server with tool registration and lifespan DB pool management.

Run: uv run --package comprende-ya-mcp python -m mcp_server.server
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import Context, FastMCP

from mcp_server.db import create_pool
from mcp_server.graph_schema import init_schema
from mcp_server.models import EvidenceEvent
from mcp_server.tools.concepts import query_concepts as _query_concepts
from mcp_server.tools.confusion_pairs import get_confusion_pairs as _get_confusion_pairs
from mcp_server.tools.effective_contexts import (
    get_effective_contexts as _get_effective_contexts,
)
from mcp_server.tools.ingest_evidence import ingest_evidence as _ingest_evidence
from mcp_server.tools.learner import get_learner_profile as _get_learner_profile
from mcp_server.tools.assess_interaction import assess_interaction as _assess_interaction
from mcp_server.tools.learner_state import get_learner_state as _get_learner_state


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
async def query_concepts(
    ctx: Context,
    cefr_level: str | None = None,
    category: str | None = None,
    concept_id: str | None = None,
) -> list[dict]:
    """Browse the Spanish concept graph. Filter by cefr_level, category, or concept_id."""
    pool = _get_pool(ctx)
    concepts = await _query_concepts(
        pool, cefr_level=cefr_level, category=category, concept_id=concept_id
    )
    return [c.model_dump() for c in concepts]


@mcp.tool
async def ingest_evidence(
    ctx: Context,
    learner_id: str,
    events: list[dict],
) -> dict:
    """Ingest a batch of evidence events and update the learner model.

    Each event: {concept_id, signal, outcome, session_id?, context_id?, activity_type?, timestamp?}
    Signals: produced_correctly, produced_with_errors, recognized, failed_to_produce,
             failed_to_recognize, self_corrected, confused_with
    """
    pool = _get_pool(ctx)
    parsed = [EvidenceEvent(**e) for e in events]
    return await _ingest_evidence(pool, learner_id=learner_id, events=parsed)


@mcp.tool
async def get_learner_state(
    ctx: Context,
    learner_id: str,
    concept_ids: list[str] | None = None,
) -> list[dict]:
    """Get current STUDIES state for a learner, with decay-projected mastery."""
    pool = _get_pool(ctx)
    states = await _get_learner_state(
        pool, learner_id=learner_id, concept_ids=concept_ids
    )
    return [s.model_dump() for s in states]


@mcp.tool
async def get_learner_profile(
    ctx: Context,
    learner_id: str,
) -> dict:
    """Get a learner's profile: mastered, progressing, decaying, unseen concepts + confusion pairs."""
    pool = _get_pool(ctx)
    profile = await _get_learner_profile(pool, learner_id=learner_id)
    return profile.model_dump()


@mcp.tool
async def get_confusion_pairs(
    ctx: Context,
    learner_id: str,
) -> list[dict]:
    """Get confusion pairs (co-failing contrasting concepts) for a learner."""
    pool = _get_pool(ctx)
    pairs = await _get_confusion_pairs(pool, learner_id=learner_id)
    return [p.model_dump() for p in pairs]


@mcp.tool
async def get_effective_contexts(
    ctx: Context,
    learner_id: str,
) -> list[dict]:
    """Get effective learning contexts for a learner (populated in Phase 3C)."""
    pool = _get_pool(ctx)
    contexts = await _get_effective_contexts(pool, learner_id=learner_id)
    return [c.model_dump() for c in contexts]


@mcp.tool
async def assess_interaction(
    ctx: Context,
    learner_id: str,
    session_id: str,
    turns: list[dict],
    target_concept_ids: list[str] | None = None,
) -> dict:
    """Assess a conversation transcript using an LLM judge.

    Each turn: {role: "learner"|"teacher", text: str, timestamp?: str, turn_index?: int}
    Produces EvidenceEvents from mastery signal analysis and ingests them into the learner model.
    """
    pool = _get_pool(ctx)
    return await _assess_interaction(
        pool,
        learner_id=learner_id,
        session_id=session_id,
        turns=turns,
        target_concept_ids=target_concept_ids,
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
