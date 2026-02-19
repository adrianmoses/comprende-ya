Refining the Graph Model
Your instinct to put mastery state on the edges is right. The key insight is that the relationship between a learner and a concept is the interesting entity, not either one in isolation. Here's how I'd structure it:
Nodes:

Learner — stays as-is
Concept — replaces your curriculum items, enriched with the metadata we discussed (cefr_range, decay_rate, typical_difficulty)
Session — stays as-is, anchors temporal context

Edges between Learner and Concept:
Rather than separate ATTEMPTED / STRUGGLED_WITH / MASTERED edge types, consider a single evolving edge type with state:
(Learner)-[:STUDIES {
  mastery: 0.0..1.0,
  confidence: 0.0..1.0,
  half_life_days: float,
  practice_count: int,
  last_evidence_at: timestamp,
  last_outcome: float,
  trend: 'rising' | 'plateau' | 'declining',
  first_seen_at: timestamp
}]->(Concept)
The reason I'd consolidate: with separate edge types, the "lifecycle" of a concept (attempted → struggled → mastered) requires creating and deleting edges, and you lose the continuous signal. A single STUDIES edge with a mastery float gives you the full spectrum, and you can still query WHERE e.mastery > 0.85 to get your "mastered" set.
That said, if you want to preserve the event log (which you should for trend analysis and debugging), keep the individual attempts as separate edges or as a related structure:
(Learner)-[:EVIDENCE {
  session_id: str,
  timestamp: datetime,
  signal: 'produced_correctly' | 'recognized' | 'failed_to_produce' | ...,
  outcome: 0.0..1.0,
  context: 'free_speech' | 'listening' | 'reading' | ...,
  activity_type: str
}]->(Concept)
So STUDIES is the aggregate state (updated after each evidence event), and EVIDENCE is the event log. The STUDIES edge is what the curriculum planner reads. The EVIDENCE edges are what you use to recompute or audit the mastery state.
Edges between Concepts:
(Concept)-[:REQUIRES]->(Concept)      -- hard prerequisite
(Concept)-[:RELATED_TO]->(Concept)    -- soft association, for transfer inference
(Concept)-[:CONTRASTS_WITH]->(Concept) -- useful for Spanish: ser/estar, por/para, indicative/subjunctive
The CONTRASTS_WITH edge is particularly valuable for language learning — these concept pairs are where learners consistently confuse things, and the planner can use them to design discrimination exercises.
What This Enables in Cypher/AGE
The graph structure makes the planner's queries very natural:
sql-- Concepts ready to advance: prerequisites met, not yet studied
SELECT * FROM cypher('learning', $$
  MATCH (l:Learner {id: $learner_id})-[:STUDIES]->(prereq:Concept)
  WHERE prereq.mastery >= 0.7
  MATCH (target:Concept)-[:REQUIRES]->(prereq)
  WHERE NOT EXISTS((l)-[:STUDIES]->(target))
  RETURN target, collect(prereq.mastery) as prereq_masteries
$$) as (target agtype, prereq_masteries agtype);

-- Concepts decaying toward review threshold
SELECT * FROM cypher('learning', $$
  MATCH (l:Learner {id: $learner_id})-[s:STUDIES]->(c:Concept)
  WHERE s.mastery * (0.5 ^ (extract(epoch FROM now() - s.last_evidence_at) 
        / 86400.0 / s.half_life_days)) < 0.5
    AND s.confidence > 0.3
  RETURN c, s.mastery, s.half_life_days, s.last_evidence_at
  ORDER BY s.mastery ASC
$$) as (concept agtype, mastery agtype, half_life agtype, last_seen agtype);
The decay computation inline is a bit ugly but avoids needing a background job to update mastery constantly. You compute the projected current mastery at query time rather than storing it eagerly.
Migrating Your Curriculum Subgraph
For transforming your existing curriculum into a concept graph, I'd approach it as:

Map your current curriculum items to concepts — some will be 1:1, others might need splitting (a "subjunctive" curriculum item probably becomes 4-6 concept nodes) or merging
Add prerequisite edges manually for the first pass — this is where your own learning experience is invaluable. You know which concepts you needed before others clicked.
Enrich with assessment signals — for each concept, define what "mastery" actually looks like across modalities (recognition, production, spontaneous use)
Backfill STUDIES edges from your existing ATTEMPTED/STRUGGLED_WITH/MASTERED data — you've already got evidence, just need to compute initial mastery estimates from it

The existing MASTERED edges give you a nice bootstrap: those concepts start with high mastery and high confidence. STRUGGLED_WITH implies low mastery but some confidence (you have evidence it's hard). Unattempted concepts get the prior only.
