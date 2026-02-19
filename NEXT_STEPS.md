# comprende-ya — Roadmap

A Spanish learning app powered by local AI: structured lessons, free conversation, and a knowledge graph tracking curriculum + learner progress.

---

## Phase 0 — Voice Pipeline Prototype (Done)

The working prototype lives in `voice-agent/`. Sub-1s latency, accurate Spanish transcription.

- [x] STT via Faster-Whisper (`small` model, CUDA, float16)
- [x] LLM via vLLM (`Llama-3.2-3B-Instruct`, half precision)
- [x] TTS via Piper CLI (Spanish voice `carlfm-x_low`)
- [x] WebSocket server (FastAPI, `/ws/voice`)
- [x] Model warmup on startup
- [x] Tuned transcription params (beam_size=5, temperature=0.0, initial_prompt)
- [x] Benchmark tooling (`benchmark.py`, `diagnostic.py`)

---

## Phase 1 — Monorepo Restructure + Webapp Scaffolding

Reorganize into a monorepo and stand up the web client.

### Target structure

```
comprende-ya/
├── mcp-server/          # KG + tools (Phase 2)
├── voice-agent/         # Current pipeline, moved here
├── webapp/              # Next.js/React client
├── shared/              # Types, utilities
└── docker-compose.yml
```

### Checklist

- [x] Create monorepo root with top-level `pyproject.toml` / workspace config
- [x] Move voice agent code into `voice-agent/` subdirectory
- [x] Update imports, paths, and CLAUDE.md references
- [x] Scaffold `webapp/` with Next.js + TypeScript
- [x] WebSocket client hook connecting to voice agent
- [x] Basic audio capture/playback in browser (AudioWorklet → PCM int16 → WS)
- [x] Health check indicator in webapp UI
- [x] CI: lint + type-check for both Python and TS

---

## Phase 2 — MCP Server + Knowledge Graph

Build the Model Context Protocol server exposing a temporal knowledge graph over PostgreSQL. Two subgraphs: **Spanish curriculum** (static) and **learner progress** (dynamic).

### Curriculum subgraph (static)

Encodes what the app can teach and how topics relate:

- Nodes: `Topic`, `Vocabulary`, `GrammarRule`, `Phrase`
- Edges: `REQUIRES` (prerequisite ordering), `CONTAINS`, `RELATED_TO`
- Seeded from a curated YAML/JSON curriculum file

### Learner subgraph (dynamic, temporal)

Tracks each learner's journey through the curriculum:

- Nodes: `Learner`, `Attempt`, `Session`
- Edges: `MASTERED`, `STRUGGLED_WITH`, `ATTEMPTED` (timestamped)
- Spaced-repetition weights derived from temporal edge data

### MCP tools exposed

| Tool | Description |
|------|-------------|
| `get_next_topics(learner_id)` | Returns recommended topics based on graph traversal |
| `record_attempt(learner_id, topic_id, result)` | Logs an attempt, updates mastery edges |
| `get_learner_profile(learner_id)` | Summary of known/weak/unseen topics |
| `query_curriculum(filter)` | Browse curriculum subgraph |
| `get_session_context(session_id)` | Retrieves conversation context for the LLM |

### Checklist

- [x] Set up `mcp-server/` with Python (FastMCP v2)
- [x] PostgreSQL + Apache AGE: graph schema with vertex/edge labels, SR relational table
- [x] Seed script for curriculum subgraph (A1-level Spanish: 4 topics)
- [x] Implement `get_next_topics` with prerequisite-aware traversal
- [x] Implement `record_attempt` with timestamp + result storage + SR updates
- [x] Implement `get_learner_profile` aggregation
- [x] Implement `query_curriculum` with filtering
- [x] Implement `get_session_context` for LLM prompt assembly
- [x] Unit tests for spaced-repetition logic, graph traversal, and tool integration
- [x] Wire MCP server into voice agent's LLM prompt pipeline

---

## Phase 3 — Concept Graph + Learner Model (Clean Break)

Replace the Phase 2 curriculum/learner subgraphs with a unified **Concept Graph** and a **Learner Model** that is the sole writer to dynamic state. This is a clean break — drop the old schema and re-seed from scratch targeting CEFR B2.

### 3A — Concept Graph (static backbone)

Simplified node model: everything teachable is a **Concept**. No separate `Topic`, `Vocabulary`, `GrammarRule`, `Phrase` node types.

**Nodes:**

| Label | Properties | Examples |
|-------|-----------|----------|
| `Concept` | `id`, `name`, `description`, `cefr_level` (A1–B2), `category` (grammar, vocabulary, pragmatics, …), `decay_rate`, `typical_difficulty`, `mastery_signals` (what "knowing this" looks like across modalities) | `subjunctive_present_regular`, `ser_vs_estar_identity`, `formal_register_usted` |
| `Context` | `id`, `name`, `register` (formal_debate, technical, casual_chat, …), `topic_domain` (travel, work, politics, …) | `casual_chat_about_travel`, `formal_debate_immigration` |

**Static edges:**

| Edge | Between | Properties | Purpose |
|------|---------|-----------|---------|
| `REQUIRES` | Concept → Concept | — | Hard prerequisite (DAG) |
| `RELATED_TO` | Concept → Concept | `strength: 0.0–1.0` | Soft association for transfer inference |
| `CONTRASTS_WITH` | Concept ↔ Concept | — | Confusion pairs: ser/estar, por/para, indicative/subjunctive |

### Checklist — 3A

- [ ] Design B2 concept taxonomy (A1→B2 progression, ~100–200 concept nodes)
- [ ] Define `mastery_signals` per concept (recognition, production, spontaneous use)
- [ ] Author `b2_seed.yaml` with concepts, prerequisites, relations, contrast pairs
- [ ] New graph schema: drop old labels, create `Concept` and `Context` vertex labels
- [ ] New seed script consuming the B2 YAML
- [ ] Validate prerequisite DAG is acyclic
- [ ] Unit tests for schema + seed integrity

### 3B — Learner Model

The Learner Model is the **sole writer** to dynamic graph state. It reads the concept graph, receives `EvidenceEvent`s, and maintains the learner's evolving relationship to every concept.

**Dynamic edges (written only by the Learner Model):**

| Edge | Between | Properties | Purpose |
|------|---------|-----------|---------|
| `STUDIES` | Learner → Concept | `mastery: 0.0–1.0`, `confidence: 0.0–1.0`, `half_life_days: float`, `practice_count: int`, `last_evidence_at: timestamp`, `last_outcome: float`, `trend: rising/plateau/declining`, `first_seen_at: timestamp` | Aggregate state — what the planner reads |
| `EVIDENCE` | Learner → Concept | `session_id`, `timestamp`, `signal` (produced_correctly, recognized, failed_to_produce, …), `outcome: 0.0–1.0`, `context_id`, `activity_type` | Immutable event log for audit + recomputation |
| `CONFUSES_WITH` | Concept ↔ Concept | `learner_id`, `evidence_count`, `last_seen_at` | Per-learner interference — created when the model detects systematic confusion between a contrast pair |
| `RESPONDS_WELL_TO` | Learner → Context | `effectiveness: 0.0–1.0`, `sample_count: int` | Tracks which communicative situations produce better learning outcomes for this learner |

**Learner Model responsibilities:**

- Receive `EvidenceEvent`s and append `EVIDENCE` edges
- Recompute `STUDIES` edge state (mastery, confidence, half-life, trend) after each evidence batch
- Handle time-based decay: projected mastery = `mastery * 0.5^(elapsed / half_life)` computed at query time
- Detect interference patterns and create/update `CONFUSES_WITH` edges
- Track context effectiveness via `RESPONDS_WELL_TO`
- Cross-concept propagation: mastering a concept boosts confidence on `RELATED_TO` neighbors

**MCP tools (Learner Model group):**

| Tool | Description |
|------|-------------|
| `ingest_evidence(learner_id, events: EvidenceEvent[])` | Batch-write evidence, recompute STUDIES state |
| `get_learner_state(learner_id, concept_ids?)` | Read STUDIES edges, with projected decay |
| `get_learner_profile(learner_id)` | Summary: mastered, progressing, decaying, unseen, confusions |
| `get_confusion_pairs(learner_id)` | Active CONFUSES_WITH edges for this learner |
| `get_effective_contexts(learner_id)` | Contexts ranked by learning effectiveness |

### Checklist — 3B

- [ ] Define `EvidenceEvent` schema (signal types, outcome scale, context reference)
- [ ] Implement `STUDIES` edge recomputation logic (replaces SM-2 relational table)
- [ ] Implement decay projection at query time (no background jobs)
- [ ] Implement `CONFUSES_WITH` detection from `CONTRASTS_WITH` + error patterns
- [ ] Implement `RESPONDS_WELL_TO` tracking
- [ ] Implement cross-concept propagation for `RELATED_TO` neighbors
- [ ] Implement all 5 Learner Model MCP tools
- [ ] Drop old SR relational table — all state lives on graph edges
- [ ] Unit tests for mastery recomputation, decay, confusion detection

### 3C — Assessment Layer (LLM-as-Judge)

Converts raw voice agent transcripts into structured `EvidenceEvent`s. Runs a **local LLM** to evaluate learner utterances against concept mastery signals.

**Input:** raw interaction events from the voice agent (transcribed utterances, conversation turns, activity outcomes)

**Output:** `EvidenceEvent`s emitted to the Learner Model via `ingest_evidence`

**What it detects:**

- Correct/incorrect production of target concepts
- Spontaneous use of concepts outside the current lesson focus
- Misconceptions and systematic errors (feeds `CONFUSES_WITH`)
- Register/context patterns (feeds `RESPONDS_WELL_TO`)

### Checklist — 3C

- [ ] Define interaction event schema (what the voice agent emits)
- [ ] Assessment prompt template: score utterances against concept `mastery_signals`
- [ ] Local LLM integration for assessment (separate from conversation LLM)
- [ ] Misconception detection logic (pattern matching across recent evidence)
- [ ] Context pattern extraction (register + topic domain from conversation)
- [ ] Pipeline: raw events → LLM judge → `EvidenceEvent[]` → `ingest_evidence()`
- [ ] Evaluation: compare LLM-judge ratings against manual annotations

### 3D — Curriculum Planner

**Read-only** consumer of the Learner Model. Produces `SessionPlan` objects that parameterize the voice agent. Operates at two timescales.

**Between sessions:** full priority scoring → `SessionPlan`

- Queries decaying concepts (review candidates)
- Queries concepts with satisfied prerequisites (advancement candidates)
- Checks `CONFUSES_WITH` for discrimination exercise opportunities
- Checks `RESPONDS_WELL_TO` for optimal context selection
- Produces ordered activity list with time estimates

**Within a session:** lightweight replanning

- If assessment reports early mastery → advance to next activity
- If assessment reports unexpected struggle → slow down, insert scaffolding
- Threshold-based, no full re-scoring

**SessionPlan structure:**

```
SessionPlan:
  learner_id: str
  activities: list[Activity]

Activity:
  concept_ids: list[str]        # target concepts
  activity_type: str            # "drill", "conversation", "discrimination", ...
  context: str                  # communicative context to use
  instructions: str             # natural language for voice agent system prompt
  duration_estimate_min: float
  contrast_pair?: str           # for discrimination exercises
```

**MCP tools (Curriculum Planner group):**

| Tool | Description |
|------|-------------|
| `plan_session(learner_id, duration_min?)` | Produce a full SessionPlan |
| `replan_activity(session_id, current_progress)` | Lightweight intra-session adjustment |
| `query_concepts(filter)` | Browse concept graph (replaces `query_curriculum`) |

### Checklist — 3D

- [ ] Implement priority scoring: decay urgency + prerequisite readiness + confusion opportunity
- [ ] Implement `plan_session` tool
- [ ] Implement `replan_activity` tool for intra-session adjustment
- [ ] Implement `query_concepts` with filtering by level, category, prerequisite status
- [ ] Activity type templates (drill, conversation, discrimination exercise)
- [ ] Context selection based on `RESPONDS_WELL_TO` effectiveness data
- [ ] Integration test: full plan → teach → assess → update → replan cycle

### 3E — Voice Agent Integration

The voice agent stays simple. It follows the session plan, produces transcripts, and emits raw interaction events. It **never touches the graph**.

**Changes to voice agent:**

- Accept `SessionPlan` and inject `Activity.instructions` into LLM system prompt
- Emit raw interaction events (timestamped utterances + metadata) to the Assessment Layer
- Support asynchronous curriculum planner queries (non-blocking)
- Respond to intra-session replan signals (swap system prompt mid-session)

### Checklist — 3E

- [ ] Define interaction event emission format
- [ ] Wire voice agent to receive `SessionPlan` from planner
- [ ] Inject activity instructions into LLM system prompt per activity
- [ ] Emit raw events to Assessment Layer (async, non-blocking)
- [ ] Handle intra-session replan: update system prompt when planner signals activity change
- [ ] Update `mcp_client.py` to call new Learner Model + Planner tools
- [ ] Remove old `record_attempt` / `get_session_context` calls

### 3F — Webapp Updates

- [ ] Mode switching UI (structured / free conversation)
- [ ] Progress dashboard: concepts mastered, decaying, confused pairs, trend charts
- [ ] Session history with evidence trail
- [ ] Context preference display (what situations work best for this learner)

---

## Phase 4 — Docker Compose + Deployment

Package everything for reproducible local and remote deployment.

### Checklist

- [ ] `voice-agent/Dockerfile` (CUDA base image, model download on build)
- [ ] `mcp-server/Dockerfile` (Python + PostgreSQL client)
- [ ] `webapp/Dockerfile` (Node.js, static export option)
- [ ] `docker-compose.yml` orchestrating all services + PostgreSQL
- [ ] Volume mounts for model caching (avoid re-downloading)
- [ ] GPU passthrough configuration (`nvidia-container-toolkit`)
- [ ] Environment variable config (model paths, ports, DB credentials)
- [ ] Health checks across all services
- [ ] README with setup instructions

---

## Open Questions

- **Model upgrade path**: When to move from Llama 3.2-3B to a larger/better model for richer conversation?
- **Assessment LLM sizing**: Is Llama 3.2-3B sufficient for LLM-as-judge, or does assessment need a more capable model (e.g., 8B)?
- **Multi-user**: Single-user first, but schema supports multiple learners from the start (STUDIES/EVIDENCE edges are per-learner).
- **Mobile**: PWA vs native? Browser audio APIs may be sufficient initially.
- **Curriculum authoring**: Manual YAML editing vs admin UI for adding concepts?
- **B2 concept granularity**: How fine-grained should concept nodes be? (e.g., one "subjunctive" node vs. 6 sub-concepts)
- **Evidence retention**: How long to keep EVIDENCE edges? Prune after recomputation, or keep indefinitely for trend analysis?
