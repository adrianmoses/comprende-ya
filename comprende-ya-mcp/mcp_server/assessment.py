"""Assessment pipeline: transcript → LLM judge → EvidenceEvent[] → ingest."""

from __future__ import annotations

import json

from mcp_server.db import cypher_query, escape_cypher
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.llm_client import JUDGE_LLM_MODEL, call_judge
from mcp_server.models import (
    AssessmentResult,
    ConceptSummary,
    EvidenceEvent,
    InteractionTurn,
)
from mcp_server.tools.concepts import query_concepts_batch
from mcp_server.tools.ingest_evidence import ingest_evidence

VALID_SIGNALS = frozenset(
    {
        "produced_correctly",
        "produced_with_errors",
        "recognized",
        "failed_to_produce",
        "failed_to_recognize",
        "self_corrected",
        "confused_with",
    }
)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def _build_system_prompt() -> str:
    return """You are a Spanish language assessment judge. Your task is to analyze a conversation between a learner and a teacher, and evaluate the learner's performance against specific concept mastery signals.

For each concept the learner demonstrates knowledge of (or fails to), emit an evidence event.

## Signal vocabulary

- `produced_correctly`: Learner used the concept correctly in their own speech.
- `produced_with_errors`: Learner attempted to use the concept but made errors.
- `recognized`: Learner understood the concept when used by the teacher.
- `failed_to_produce`: Learner should have used the concept but didn't or couldn't.
- `failed_to_recognize`: Learner failed to understand the concept when used by teacher.
- `self_corrected`: Learner initially made an error but corrected themselves.
- `confused_with`: Learner confused this concept with another concept (specify which via `confused_with_concept_id`).

## Outcome scale

- 1.0: Perfect demonstration of mastery.
- 0.8: Minor hesitation or slight imperfection.
- 0.6: Partially correct, noticeable errors.
- 0.4: Significant errors but some understanding shown.
- 0.2: Major errors, minimal understanding.
- 0.0: Complete failure or no attempt.

## Context extraction

Identify the conversational context/register from the conversation (e.g. "ordering_food", "giving_directions", "casual_chat", "formal_introduction"). Return this as `context_id`.

## Response format

Return a JSON object with this exact structure:
```json
{
  "context_id": "string or null",
  "events": [
    {
      "concept_id": "string",
      "signal": "string (from signal vocabulary)",
      "outcome": 0.0,
      "turn_index": 0,
      "confused_with_concept_id": "string or null"
    }
  ]
}
```

Rules:
- Only emit events for concepts provided in the concept list.
- Each event must reference a specific `turn_index` from the conversation.
- Only assess learner turns, not teacher turns.
- If `confused_with` signal is used, `confused_with_concept_id` must reference another concept from the provided list.
- Be conservative: only emit events where there is clear evidence."""


def _build_user_prompt(
    concepts: list[ConceptSummary],
    turns: list[InteractionTurn],
) -> str:
    lines = ["## Concepts to assess\n"]
    for c in concepts:
        block = f"- **{c.id}** ({c.name}): {c.description}"
        if c.mastery_signals:
            block += f"\n  Mastery signals: {', '.join(c.mastery_signals)}"
        if c.contrasts_with:
            block += f"\n  Contrasts with: {', '.join(c.contrasts_with)}"
        lines.append(block)

    lines.append("\n## Conversation transcript\n")
    for t in turns:
        label = "LEARNER" if t.role == "learner" else "TEACHER"
        lines.append(f"[Turn {t.turn_index}] {label}: {t.text}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_assessment_response(
    raw: str,
    valid_concept_ids: set[str],
    turns: list[InteractionTurn],
    session_id: str,
) -> tuple[list[EvidenceEvent], str | None, list[str]]:
    """Parse the judge LLM response into EvidenceEvents.

    Returns: (events, context_id, errors)
    """
    errors: list[str] = []

    # Try to extract JSON from potentially prose-wrapped output
    data = _extract_json(raw)
    if data is None:
        errors.append(f"Failed to parse JSON from judge response: {raw[:200]}")
        return [], None, errors

    context_id = data.get("context_id")
    raw_events = data.get("events", [])
    if not isinstance(raw_events, list):
        errors.append(f"'events' field is not a list: {type(raw_events)}")
        return [], context_id, errors

    # Build turn timestamp map
    ts_map: dict[int, str | None] = {t.turn_index: t.timestamp for t in turns}

    events: list[EvidenceEvent] = []
    seen: set[tuple[str, int]] = set()

    for i, raw_ev in enumerate(raw_events):
        if not isinstance(raw_ev, dict):
            errors.append(f"Event {i} is not a dict")
            continue

        concept_id = raw_ev.get("concept_id", "")
        if concept_id not in valid_concept_ids:
            errors.append(f"Event {i}: unknown concept_id '{concept_id}', dropped")
            continue

        signal = raw_ev.get("signal", "produced_with_errors")
        if signal not in VALID_SIGNALS:
            errors.append(
                f"Event {i}: unknown signal '{signal}', defaulting to 'produced_with_errors'"
            )
            signal = "produced_with_errors"

        outcome = raw_ev.get("outcome", 0.5)
        try:
            outcome = float(outcome)
        except (TypeError, ValueError):
            outcome = 0.5
        outcome = max(0.0, min(1.0, outcome))

        turn_index = raw_ev.get("turn_index", 0)
        try:
            turn_index = int(turn_index)
        except (TypeError, ValueError):
            turn_index = 0

        # Dedup by (concept_id, turn_index)
        key = (concept_id, turn_index)
        if key in seen:
            errors.append(
                f"Event {i}: duplicate (concept_id={concept_id}, turn_index={turn_index}), dropped"
            )
            continue
        seen.add(key)

        timestamp = ts_map.get(turn_index)

        events.append(
            EvidenceEvent(
                concept_id=concept_id,
                signal=signal,
                outcome=outcome,
                session_id=session_id,
                context_id=context_id,
                timestamp=timestamp,
            )
        )

        # confused_with → emit partner event
        confused_with = raw_ev.get("confused_with_concept_id")
        if (
            signal == "confused_with"
            and confused_with
            and confused_with in valid_concept_ids
        ):
            partner_key = (confused_with, turn_index)
            if partner_key not in seen:
                seen.add(partner_key)
                events.append(
                    EvidenceEvent(
                        concept_id=confused_with,
                        signal="confused_with",
                        outcome=outcome,
                        session_id=session_id,
                        context_id=context_id,
                        timestamp=timestamp,
                    )
                )

    return events, context_id, errors


def _extract_json(raw: str) -> dict | None:
    """Extract a JSON object from a string that may contain prose around it."""
    # Try direct parse first
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Find the first '{' and walk forward counting braces to find the matching '}'
    start = raw.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            if in_string:
                escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(raw[start : i + 1])
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    break

    return None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def run_assessment(
    pool,
    learner_id: str,
    session_id: str,
    turns: list[InteractionTurn],
    target_concept_ids: list[str] | None = None,
) -> AssessmentResult:
    """Run the full assessment pipeline.

    1. Fetch concepts (targeted or recently studied)
    2. Build prompt + call judge LLM
    3. Parse response → EvidenceEvent[]
    4. Ingest evidence
    5. Return result
    """
    errors: list[str] = []

    # 1. Fetch concepts
    if target_concept_ids:
        concepts = await query_concepts_batch(pool, target_concept_ids)
    else:
        # Get 20 most recently studied concepts for this learner
        concepts = await _get_recent_concepts(pool, learner_id, limit=20)

    if not concepts:
        return AssessmentResult(
            session_id=session_id,
            learner_id=learner_id,
            turns_assessed=len(turns),
            evidence_events_created=0,
            errors=["No concepts found to assess against"],
        )

    valid_ids = {c.id for c in concepts}

    # 2. Build prompt + call judge
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(concepts, turns)

    try:
        raw_response = await call_judge(system_prompt, user_prompt)
    except Exception as e:
        return AssessmentResult(
            session_id=session_id,
            learner_id=learner_id,
            turns_assessed=len(turns),
            evidence_events_created=0,
            judge_model=JUDGE_LLM_MODEL,
            errors=[f"Judge LLM call failed: {e}"],
        )

    # 3. Parse response
    evidence_events, context_id, parse_errors = parse_assessment_response(
        raw_response, valid_ids, turns, session_id
    )
    errors.extend(parse_errors)

    if not evidence_events:
        return AssessmentResult(
            session_id=session_id,
            learner_id=learner_id,
            turns_assessed=len(turns),
            evidence_events_created=0,
            concepts_assessed=[],
            context_id=context_id,
            judge_model=JUDGE_LLM_MODEL,
            errors=errors,
        )

    # 4. Ingest evidence
    ingest_result = await ingest_evidence(
        pool, learner_id=learner_id, events=evidence_events
    )

    # 5. Build result
    concepts_assessed = list({e.concept_id for e in evidence_events})

    return AssessmentResult(
        session_id=session_id,
        learner_id=learner_id,
        turns_assessed=len(turns),
        evidence_events_created=len(evidence_events),
        concepts_assessed=concepts_assessed,
        context_id=context_id,
        studies_updated=ingest_result.get("studies_updated", []),
        confusions_detected=ingest_result.get("confusions_detected", []),
        judge_model=JUDGE_LLM_MODEL,
        errors=errors,
    )


async def _get_recent_concepts(
    pool, learner_id: str, limit: int = 20
) -> list[ConceptSummary]:
    """Get the most recently studied concepts for a learner."""
    lid = escape_cypher(learner_id)
    async with pool.connection() as conn:
        rows = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (l:Learner {{id: '{lid}'}})-[r:STUDIES]->(c:Concept) "
            f"RETURN c.id ORDER BY r.last_evidence_at DESC LIMIT {int(limit)}",
        )

    concept_ids = [str(r) for r in rows]
    if not concept_ids:
        return []

    return await query_concepts_batch(pool, concept_ids)
