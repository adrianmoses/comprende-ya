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

- [ ] Set up `mcp-server/` with Python (FastMCP or similar)
- [ ] PostgreSQL schema: nodes table, edges table, temporal columns
- [ ] Seed script for curriculum subgraph (A1-level Spanish to start)
- [ ] Implement `get_next_topics` with prerequisite-aware traversal
- [ ] Implement `record_attempt` with timestamp + result storage
- [ ] Implement `get_learner_profile` aggregation
- [ ] Implement `query_curriculum` with filtering
- [ ] Implement `get_session_context` for LLM prompt assembly
- [ ] Unit tests for graph traversal and spaced-repetition logic
- [ ] Wire MCP server into voice agent's LLM prompt pipeline

---

## Phase 3 — Structured Lessons + Free Conversation

Two interaction modes, both using the voice pipeline and knowledge graph.

### Structured lessons

- LLM receives lesson plan from `get_next_topics` + `get_session_context`
- Guided exercises: vocabulary drills, grammar prompts, fill-in-the-blank
- After each exchange, `record_attempt` updates the learner graph
- Lesson ends when topic objectives are met or time limit reached

### Free conversation

- Open-ended Spanish conversation with the LLM
- LLM system prompt tuned for natural dialogue at learner's level
- Post-conversation analysis: extract topics practiced, log attempts
- Surface corrections gently inline (not interrupting flow)

### Checklist

- [ ] Lesson planner: assembles LLM system prompt from KG context
- [ ] Exercise templates (vocabulary, grammar, listening comprehension)
- [ ] Mode switching in webapp UI (structured / free conversation)
- [ ] Post-conversation analysis pipeline (extract topics → `record_attempt`)
- [ ] Inline correction strategy for free conversation
- [ ] Progress dashboard in webapp (topics mastered, streaks, weak areas)

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
- **Multi-user**: Single-user first, but schema should support multiple learners from the start.
- **Mobile**: PWA vs native? Browser audio APIs may be sufficient initially.
- **Curriculum authoring**: Manual YAML editing vs admin UI for adding lessons?
