"""Curriculum planner MCP tool wrappers — fetch DB state, delegate to pure logic."""

from __future__ import annotations

import asyncio

from mcp_server.models import PlannerProgress, SessionPlan
from mcp_server.planner import build_session_plan, replan
from mcp_server.tools.concepts import query_concepts_batch
from mcp_server.tools.confusion_pairs import get_confusion_pairs
from mcp_server.tools.effective_contexts import get_effective_contexts
from mcp_server.tools.learner import get_learner_profile
from mcp_server.tools.learner_state import get_learner_state


async def plan_session(
    pool,
    learner_id: str,
    duration_min: float = 30.0,
) -> dict:
    """Produce a full SessionPlan for a learner.

    1. Fetch learner profile, state, confusion pairs, effective contexts (parallel)
    2. Fetch concept details for all relevant concepts
    3. Delegate to pure build_session_plan()
    """
    profile, states, confusions, contexts = await asyncio.gather(
        get_learner_profile(pool, learner_id=learner_id),
        get_learner_state(pool, learner_id=learner_id),
        get_confusion_pairs(pool, learner_id=learner_id),
        get_effective_contexts(pool, learner_id=learner_id),
    )

    # Collect all concept IDs we need details for
    all_ids = set()
    all_ids.update(profile.mastered)
    all_ids.update(profile.progressing)
    all_ids.update(profile.decaying)
    all_ids.update(profile.unseen)
    for pair in confusions:
        all_ids.add(pair.concept_a)
        all_ids.add(pair.concept_b)

    concepts = await query_concepts_batch(pool, list(all_ids)) if all_ids else []

    plan = build_session_plan(
        learner_id=learner_id,
        concepts=concepts,
        states=states,
        confusion_pairs=confusions,
        effective_contexts=contexts,
        duration_target_min=duration_min,
    )

    return plan.model_dump()


async def replan_activity(
    pool,
    learner_id: str,
    session_plan: dict,
    progress: dict,
) -> dict:
    """Lightweight intra-session replanning.

    1. Parse SessionPlan + PlannerProgress from dicts
    2. Delegate to pure replan()
    """
    plan = SessionPlan(**session_plan)
    prog = PlannerProgress(**progress)

    result = replan(plan, prog)
    return result.model_dump()
