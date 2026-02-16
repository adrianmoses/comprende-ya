"""record_attempt tool — log an attempt and update SR state."""

from __future__ import annotations

from datetime import datetime, timezone

from mcp_server.db import cypher_query
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.models import AttemptResult
from mcp_server.spaced_repetition import SRState, update_sr


async def record_attempt(
    pool,
    learner_id: str,
    topic_id: str,
    result: str,
    details: str | None = None,
) -> AttemptResult:
    """Record a learning attempt and update spaced repetition state.

    Args:
        pool: Database connection pool.
        learner_id: The learner's id.
        topic_id: The topic being practiced.
        result: "correct" or "incorrect".
        details: Optional details about the attempt.
    """
    quality = 4 if result == "correct" else 1
    now = datetime.now(timezone.utc)

    async with pool.connection() as conn:
        # Ensure learner node exists
        learners = await cypher_query(
            conn, GRAPH_NAME, f"MATCH (l:Learner {{id: '{learner_id}'}}) RETURN l"
        )
        if not learners:
            await cypher_query(
                conn,
                GRAPH_NAME,
                f"CREATE (:Learner {{id: '{learner_id}', name: '{learner_id}', "
                f"created_at: '{now.isoformat()}'}})",
            )

        # Create Attempt vertex
        attempt_id = f"attempt_{learner_id}_{topic_id}_{int(now.timestamp())}"
        await cypher_query(
            conn,
            GRAPH_NAME,
            f"CREATE (:Attempt {{id: '{attempt_id}', learner_id: '{learner_id}', "
            f"topic_id: '{topic_id}', result: '{result}', "
            f"timestamp: '{now.isoformat()}'}})",
        )

        # Create ATTEMPTED edge (Learner -> Attempt)
        await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (l:Learner {{id: '{learner_id}'}}), (a:Attempt {{id: '{attempt_id}'}}) "
            f"CREATE (l)-[:ATTEMPTED]->(a)",
        )

        # Create ATTEMPT_OF edge (Attempt -> Topic)
        await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (a:Attempt {{id: '{attempt_id}'}}), (t:Topic {{id: '{topic_id}'}}) "
            f"CREATE (a)-[:ATTEMPT_OF]->(t)",
        )

        # Get current SR state from relational table
        row = await conn.execute(
            "SELECT ease_factor, interval_days, repetitions, next_review, last_attempt "
            "FROM spaced_repetition WHERE learner_id = %s AND topic_id = %s",
            (learner_id, topic_id),
        )
        existing = await row.fetchone()

        if existing:
            current_state = SRState(
                ease_factor=existing[0],
                interval_days=existing[1],
                repetitions=existing[2],
                next_review=existing[3],
                last_attempt=existing[4],
            )
        else:
            current_state = SRState()

        # Update SR
        new_state = update_sr(current_state, quality)

        # Upsert into spaced_repetition table
        await conn.execute(
            """
            INSERT INTO spaced_repetition
                (learner_id, topic_id, ease_factor, interval_days, repetitions, next_review, last_attempt)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (learner_id, topic_id) DO UPDATE SET
                ease_factor = EXCLUDED.ease_factor,
                interval_days = EXCLUDED.interval_days,
                repetitions = EXCLUDED.repetitions,
                next_review = EXCLUDED.next_review,
                last_attempt = EXCLUDED.last_attempt
            """,
            (
                learner_id,
                topic_id,
                new_state.ease_factor,
                new_state.interval_days,
                new_state.repetitions,
                new_state.next_review,
                new_state.last_attempt,
            ),
        )

        # Update graph edges: MASTERED / STRUGGLED_WITH
        next_review_iso = (
            new_state.next_review.isoformat() if new_state.next_review else ""
        )
        if result == "correct" and new_state.repetitions >= 2:
            # Remove STRUGGLED_WITH if exists
            await cypher_query(
                conn,
                GRAPH_NAME,
                f"MATCH (l:Learner {{id: '{learner_id}'}})"
                f"-[r:STRUGGLED_WITH]->"
                f"(t:Topic {{id: '{topic_id}'}}) DELETE r",
            )
            # Create or update MASTERED edge
            mastered = await cypher_query(
                conn,
                GRAPH_NAME,
                f"MATCH (l:Learner {{id: '{learner_id}'}})"
                f"-[r:MASTERED]->"
                f"(t:Topic {{id: '{topic_id}'}}) RETURN r",
            )
            if mastered:
                await cypher_query(
                    conn,
                    GRAPH_NAME,
                    f"MATCH (l:Learner {{id: '{learner_id}'}})"
                    f"-[r:MASTERED]->"
                    f"(t:Topic {{id: '{topic_id}'}}) "
                    f"SET r.ease_factor = {new_state.ease_factor}, "
                    f"r.interval_days = {new_state.interval_days}, "
                    f"r.repetitions = {new_state.repetitions}, "
                    f"r.next_review = '{next_review_iso}'",
                )
            else:
                await cypher_query(
                    conn,
                    GRAPH_NAME,
                    f"MATCH (l:Learner {{id: '{learner_id}'}}), (t:Topic {{id: '{topic_id}'}}) "
                    f"CREATE (l)-[:MASTERED {{ease_factor: {new_state.ease_factor}, "
                    f"interval_days: {new_state.interval_days}, "
                    f"repetitions: {new_state.repetitions}, "
                    f"next_review: '{next_review_iso}'}}]->(t)",
                )
        elif result == "incorrect":
            struggled = await cypher_query(
                conn,
                GRAPH_NAME,
                f"MATCH (l:Learner {{id: '{learner_id}'}})"
                f"-[r:STRUGGLED_WITH]->"
                f"(t:Topic {{id: '{topic_id}'}}) RETURN r",
            )
            if struggled:
                await cypher_query(
                    conn,
                    GRAPH_NAME,
                    f"MATCH (l:Learner {{id: '{learner_id}'}})"
                    f"-[r:STRUGGLED_WITH]->"
                    f"(t:Topic {{id: '{topic_id}'}}) "
                    f"SET r.last_attempt = '{now.isoformat()}', "
                    f"r.fail_count = r.fail_count + 1",
                )
            else:
                await cypher_query(
                    conn,
                    GRAPH_NAME,
                    f"MATCH (l:Learner {{id: '{learner_id}'}}), (t:Topic {{id: '{topic_id}'}}) "
                    f"CREATE (l)-[:STRUGGLED_WITH {{last_attempt: '{now.isoformat()}', "
                    f"fail_count: 1}}]->(t)",
                )

        return AttemptResult(
            learner_id=learner_id,
            topic_id=topic_id,
            result=result,
            new_interval_days=new_state.interval_days,
            new_ease_factor=new_state.ease_factor,
            next_review=new_state.next_review.isoformat()
            if new_state.next_review
            else "",
        )
