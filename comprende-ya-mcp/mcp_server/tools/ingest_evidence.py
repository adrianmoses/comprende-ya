"""ingest_evidence tool — main write path for the learner model."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mcp_server.db import cypher_query, escape_cypher
from mcp_server.graph_schema import GRAPH_NAME
from mcp_server.learner_model import (
    CONFUSION_OUTCOME_THRESHOLD,
    CONFUSION_WINDOW_DAYS,
    HALF_LIFE_INIT,
    compute_confidence,
    compute_propagation,
    compute_trend,
    detect_confusions,
    recompute_studies,
)
from mcp_server.models import EvidenceEvent


async def ingest_evidence(
    pool,
    learner_id: str,
    events: list[EvidenceEvent],
) -> dict:
    """Ingest a batch of evidence events and update the learner model.

    Returns: {processed, studies_updated, confusions_detected}
    """
    now = datetime.now(timezone.utc)
    studies_updated = []
    confusions_detected = []

    async with pool.connection() as conn:
        # Ensure Learner node exists
        learners = await cypher_query(
            conn,
            GRAPH_NAME,
            f"MATCH (l:Learner {{id: '{escape_cypher(learner_id)}'}}) RETURN l",
        )
        if not learners:
            await cypher_query(
                conn,
                GRAPH_NAME,
                f"CREATE (:Learner {{id: '{escape_cypher(learner_id)}', "
                f"created_at: '{now.isoformat()}'}})",
            )

        for event in events:
            ts = event.timestamp or now.isoformat()
            cid = escape_cypher(event.concept_id)
            lid = escape_cypher(learner_id)

            # 1. Create EVIDENCE edge (immutable, append-only)
            evidence_props = (
                f"signal: '{escape_cypher(event.signal)}', "
                f"outcome: {event.outcome}, "
                f"timestamp: '{ts}'"
            )
            if event.session_id:
                evidence_props += f", session_id: '{escape_cypher(event.session_id)}'"
            if event.context_id:
                evidence_props += f", context_id: '{escape_cypher(event.context_id)}'"
            if event.activity_type:
                evidence_props += (
                    f", activity_type: '{escape_cypher(event.activity_type)}'"
                )

            await cypher_query(
                conn,
                GRAPH_NAME,
                f"MATCH (l:Learner {{id: '{lid}'}}), (c:Concept {{id: '{cid}'}}) "
                f"CREATE (l)-[:EVIDENCE {{{evidence_props}}}]->(c)",
            )

            # 2. Read current STUDIES edge
            studies_rows = await cypher_query(
                conn,
                GRAPH_NAME,
                f"MATCH (l:Learner {{id: '{lid}'}})"
                f"-[r:STUDIES]->"
                f"(c:Concept {{id: '{cid}'}}) RETURN r",
            )

            if studies_rows:
                s = studies_rows[0]
                props = s.get("properties", s) if isinstance(s, dict) else s
                cur_mastery = float(props.get("mastery", 0.0))
                cur_hl = float(props.get("half_life_days", HALF_LIFE_INIT))
                cur_pc = int(props.get("practice_count", 0))
                first_seen = props.get("first_seen_at", ts)
                last_at = props.get("last_evidence_at", ts)
            else:
                cur_mastery = 0.0
                cur_hl = HALF_LIFE_INIT
                cur_pc = 0
                first_seen = ts
                last_at = ts

            # Compute elapsed days
            try:
                last_dt = datetime.fromisoformat(last_at)
                ts_dt = datetime.fromisoformat(ts)
                elapsed = max(0.0, (ts_dt - last_dt).total_seconds() / 86400.0)
            except (ValueError, TypeError):
                elapsed = 0.0

            # 3. Fetch EVIDENCE outcomes ordered by timestamp for trend/confidence
            recent_rows = await cypher_query(
                conn,
                GRAPH_NAME,
                f"MATCH (l:Learner {{id: '{lid}'}})"
                f"-[e:EVIDENCE]->"
                f"(c:Concept {{id: '{cid}'}}) RETURN e ORDER BY e.timestamp",
            )
            recent_outcomes: list[tuple[str, float]] = []
            for r in recent_rows:
                rp = r.get("properties", r) if isinstance(r, dict) else r
                recent_outcomes.append(
                    (
                        str(rp.get("timestamp", "")),
                        float(rp.get("outcome", 0.0)),
                    )
                )
            # Sort by timestamp as safety net (AGE ORDER BY may vary)
            recent_outcomes.sort(key=lambda x: x[0])
            recent_for_trend = [o for _, o in recent_outcomes[-5:]]

            # 4. Recompute STUDIES
            new_state = recompute_studies(
                mastery=cur_mastery,
                half_life_days=cur_hl,
                practice_count=cur_pc,
                outcome=event.outcome,
                elapsed_days=elapsed,
            )
            mastery_delta = new_state["mastery"] - cur_mastery

            trend = compute_trend(recent_for_trend)
            confidence = compute_confidence(
                new_state["practice_count"], recent_for_trend
            )

            # 5. Upsert STUDIES edge
            studies_vals = {
                "mastery": new_state["mastery"],
                "half_life_days": new_state["half_life_days"],
                "practice_count": new_state["practice_count"],
                "confidence": confidence,
                "trend": trend,
                "last_evidence_at": ts,
                "last_outcome": event.outcome,
                "first_seen_at": first_seen,
            }

            if studies_rows:
                set_clause = ", ".join(
                    f"r.{k} = '{v}'" if isinstance(v, str) else f"r.{k} = {v}"
                    for k, v in studies_vals.items()
                )
                await cypher_query(
                    conn,
                    GRAPH_NAME,
                    f"MATCH (l:Learner {{id: '{lid}'}})"
                    f"-[r:STUDIES]->"
                    f"(c:Concept {{id: '{cid}'}}) "
                    f"SET {set_clause}",
                )
            else:
                props_str = ", ".join(
                    f"{k}: '{v}'" if isinstance(v, str) else f"{k}: {v}"
                    for k, v in studies_vals.items()
                )
                await cypher_query(
                    conn,
                    GRAPH_NAME,
                    f"MATCH (l:Learner {{id: '{lid}'}}), (c:Concept {{id: '{cid}'}}) "
                    f"CREATE (l)-[:STUDIES {{{props_str}}}]->(c)",
                )

            studies_updated.append(
                {
                    "concept_id": event.concept_id,
                    "mastery": new_state["mastery"],
                    "projected_mastery": new_state[
                        "mastery"
                    ],  # no decay yet, just updated
                    "trend": trend,
                }
            )

            # 6. Confusion detection
            if event.outcome < 0.4 or event.signal == "confused_with":
                # Get CONTRASTS_WITH partners
                contrast_rows = await cypher_query(
                    conn,
                    GRAPH_NAME,
                    f"MATCH (c:Concept {{id: '{cid}'}})-[:CONTRASTS_WITH]-(p:Concept) "
                    f"RETURN p.id",
                )
                contrast_partners = [
                    r if isinstance(r, str) else r for r in contrast_rows
                ]

                if contrast_partners:
                    # Count failures within the confusion window per concept
                    window_cutoff = (
                        now - timedelta(days=CONFUSION_WINDOW_DAYS)
                    ).isoformat()
                    recent_failures: dict[str, int] = {}
                    for partner_id in contrast_partners + [event.concept_id]:
                        pid = escape_cypher(partner_id)
                        fail_rows = await cypher_query(
                            conn,
                            GRAPH_NAME,
                            f"MATCH (l:Learner {{id: '{lid}'}})"
                            f"-[e:EVIDENCE]->"
                            f"(c:Concept {{id: '{pid}'}}) RETURN e",
                        )
                        count = 0
                        for fr in fail_rows:
                            fp = (
                                fr.get("properties", fr) if isinstance(fr, dict) else fr
                            )
                            ev_ts = str(fp.get("timestamp", ""))
                            if ev_ts < window_cutoff:
                                continue
                            if (
                                float(fp.get("outcome", 1.0))
                                < CONFUSION_OUTCOME_THRESHOLD
                            ):
                                count += 1
                        recent_failures[partner_id] = count

                    pairs = detect_confusions(
                        event.concept_id,
                        event.outcome,
                        contrast_partners,
                        recent_failures,
                    )

                    for a, b in pairs:
                        ea, eb = escape_cypher(a), escape_cypher(b)
                        # Check if CONFUSES_WITH already exists
                        existing = await cypher_query(
                            conn,
                            GRAPH_NAME,
                            f"MATCH (l:Learner {{id: '{lid}'}})"
                            f"-[r:CONFUSES_WITH {{concept_a: '{ea}', concept_b: '{eb}'}}]->"
                            f"(l) RETURN r",
                        )
                        if existing:
                            ep = existing[0]
                            ep_props = (
                                ep.get("properties", ep) if isinstance(ep, dict) else ep
                            )
                            ec = int(ep_props.get("evidence_count", 0)) + 1
                            await cypher_query(
                                conn,
                                GRAPH_NAME,
                                f"MATCH (l:Learner {{id: '{lid}'}})"
                                f"-[r:CONFUSES_WITH {{concept_a: '{ea}', concept_b: '{eb}'}}]->"
                                f"(l) "
                                f"SET r.evidence_count = {ec}, "
                                f"r.last_seen_at = '{ts}'",
                            )
                        else:
                            await cypher_query(
                                conn,
                                GRAPH_NAME,
                                f"MATCH (l:Learner {{id: '{lid}'}}) "
                                f"CREATE (l)-[:CONFUSES_WITH {{"
                                f"concept_a: '{ea}', concept_b: '{eb}', "
                                f"evidence_count: 1, last_seen_at: '{ts}'"
                                f"}}]->(l)",
                            )
                        confusions_detected.append({"concept_a": a, "concept_b": b})

            # 7. Cross-concept propagation
            if mastery_delta > 0.1:
                related_rows = await cypher_query(
                    conn,
                    GRAPH_NAME,
                    f"MATCH (c:Concept {{id: '{cid}'}})-[r:RELATED_TO]-(p:Concept) "
                    f"RETURN p.id, r.strength",
                    columns=["pid", "strength"],
                )
                related = [
                    (pid, float(strength) if strength else 0.5)
                    for pid, strength in related_rows
                ]
                boosts = compute_propagation(mastery_delta, related)

                for neighbor_id, boost in boosts:
                    nid = escape_cypher(neighbor_id)
                    # Only boost if STUDIES edge exists
                    neighbor_studies = await cypher_query(
                        conn,
                        GRAPH_NAME,
                        f"MATCH (l:Learner {{id: '{lid}'}})"
                        f"-[r:STUDIES]->"
                        f"(c:Concept {{id: '{nid}'}}) RETURN r",
                    )
                    if neighbor_studies:
                        ns = neighbor_studies[0]
                        ns_props = (
                            ns.get("properties", ns) if isinstance(ns, dict) else ns
                        )
                        cur_conf = float(ns_props.get("confidence", 0.0))
                        cur_m = float(ns_props.get("mastery", 0.0))
                        # Cap boost: confidence can't exceed neighbor's mastery
                        new_conf = min(cur_m, cur_conf + boost)
                        await cypher_query(
                            conn,
                            GRAPH_NAME,
                            f"MATCH (l:Learner {{id: '{lid}'}})"
                            f"-[r:STUDIES]->"
                            f"(c:Concept {{id: '{nid}'}}) "
                            f"SET r.confidence = {round(new_conf, 4)}",
                        )

            # 8. Context tracking (no-op when context_id is null)
            if event.context_id:
                ctx_id = escape_cypher(event.context_id)
                ctx_rows = await cypher_query(
                    conn,
                    GRAPH_NAME,
                    f"MATCH (l:Learner {{id: '{lid}'}})"
                    f"-[r:RESPONDS_WELL_TO {{context_id: '{ctx_id}'}}]->"
                    f"(l) RETURN r",
                )
                if ctx_rows:
                    cp = ctx_rows[0]
                    cp_props = cp.get("properties", cp) if isinstance(cp, dict) else cp
                    old_eff = float(cp_props.get("effectiveness", 0.0))
                    old_count = int(cp_props.get("sample_count", 0))
                    new_count = old_count + 1
                    # Running average of outcomes
                    new_eff = (old_eff * old_count + event.outcome) / new_count
                    await cypher_query(
                        conn,
                        GRAPH_NAME,
                        f"MATCH (l:Learner {{id: '{lid}'}})"
                        f"-[r:RESPONDS_WELL_TO {{context_id: '{ctx_id}'}}]->"
                        f"(l) "
                        f"SET r.effectiveness = {round(new_eff, 4)}, "
                        f"r.sample_count = {new_count}",
                    )
                else:
                    await cypher_query(
                        conn,
                        GRAPH_NAME,
                        f"MATCH (l:Learner {{id: '{lid}'}}) "
                        f"CREATE (l)-[:RESPONDS_WELL_TO {{"
                        f"context_id: '{ctx_id}', "
                        f"effectiveness: {event.outcome}, "
                        f"sample_count: 1"
                        f"}}]->(l)",
                    )

    return {
        "processed": len(events),
        "studies_updated": studies_updated,
        "confusions_detected": confusions_detected,
    }
