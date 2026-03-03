# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spanish learning app powered by local AI. Monorepo with a voice agent (Python), web client (Next.js), and MCP server (knowledge graph + curriculum).

## Monorepo Structure

```
comprende-ya/
├── voice-agent/        # Pipecat voice pipeline (Python/uv)
├── webapp/             # Next.js web client (pnpm)
├── comprende-ya-mcp/   # Knowledge graph MCP server (FastMCP + PostgreSQL/AGE)
├── pyproject.toml      # Root uv workspace
├── models/             # GGUF model files for llama-server
└── docker-compose.yml  # PostgreSQL + AGE (5455) + llama-server (8081, 8082)
```

## Commands

```bash
# Python workspace (from repo root)
uv sync --all-packages                           # Install all Python deps
uv run --package voice-agent python voice-agent/voice_agent_pipecat.py  # Start voice agent (Pipecat)
uv run ruff check voice-agent/                   # Lint Python
uv run ruff format voice-agent/                  # Format Python
uv run mypy voice-agent/ --ignore-missing-imports # Type-check Python

# Webapp (from webapp/)
cd webapp && pnpm install                         # Install JS deps
cd webapp && pnpm dev                             # Dev server on port 3000
cd webapp && pnpm lint                            # ESLint
cd webapp && pnpm tsc --noEmit                    # Type-check TypeScript

# Voice agent scripts (from repo root)
uv run --package voice-agent python voice-agent/test_client.py    # Mic test
uv run --package voice-agent python voice-agent/benchmark.py      # Benchmark
uv run --package voice-agent python voice-agent/diagnostic.py     # Diagnostics

# MCP server (from repo root)
docker compose up -d                                              # Start AGE database + llama-server
uv run --package comprende-ya-mcp python -m mcp_server.seed             # Seed A1 curriculum (legacy)
uv run --package comprende-ya-mcp python -m mcp_server.b2_seed          # Seed B2 concept graph (drops + recreates)
uv run --package comprende-ya-mcp python -m mcp_server.server           # Start MCP server (port 8001)
uv run ruff check comprende-ya-mcp/                                     # Lint MCP server
uv run ruff format comprende-ya-mcp/                                    # Format MCP server
uv run mypy comprende-ya-mcp/mcp_server/ --ignore-missing-imports       # Type-check MCP server
uv run --package comprende-ya-mcp pytest comprende-ya-mcp/tests/ -v           # Run tests
```

## Architecture

**Voice pipeline** (Pipecat): Continuous audio stream → VAD → STT → LLM (streaming) → TTS → Audio response

- **Framework**: Pipecat pipeline with Smart Turn v3.2 for natural turn-taking (no press-to-talk)
- **VAD**: Silero VAD for speech activity detection
- **STT**: Faster-Whisper (`medium` model, CUDA, float16) via Pipecat WhisperSTTService
- **LLM (voice)**: llama-server (`Llama-3.2-3B-Instruct` GGUF Q8_0) via OpenAI-compatible API on `:8081`
- **LLM (judge)**: llama-server (`Meta-Llama-3.1-8B-Instruct` GGUF Q4_K_M) on `:8082` — dedicated to assessment
- **TTS**: Piper via Pipecat PiperTTSService (Spanish voice model, loads .onnx directly)
- **Turn detection**: Smart Turn v3.2 — 8MB ONNX model analyzing prosody/grammar cues (~12ms inference on CPU)
- Voice agent and assessment judge use separate llama-server instances to avoid contention

**Server**: FastAPI with WebSocket (Pipecat transport) + REST endpoints
- WebSocket `/ws/voice`: continuous int16 audio streaming, Pipecat pipeline per connection
- Pipeline: `transport.input() → STT → TranscriptionObserver → UserAggregator → LLM → TTS → SessionInterceptor → transport.output() → AssistantAggregator`
- Custom `ComprendeSerializer` bridges webapp PCM+JSON protocol with Pipecat frames
- REST session lifecycle: `POST /session/start`, `POST /session/end`, `GET /session/state`
- REST learner proxy: `GET /learner/profile`, `GET /learner/state`, `GET /learner/confusions`, `GET /learner/contexts`
- Health endpoint returns 503 during model warmup (lifespan-based warmup with ready gating)
- Session manager (`session_manager.py`): handles structured/free modes, activity transitions, assessment firing

**MCP Server**: FastMCP with PostgreSQL + Apache AGE (Cypher graph queries)
- Concept graph: 53 B2-level Concept nodes with REQUIRES (DAG), RELATED_TO, CONTRASTS_WITH edges
- Context nodes: label created, population deferred to Phase 3C
- Learner model: STUDIES edges (half-life decay mastery), EVIDENCE edges (immutable event log), CONFUSES_WITH, RESPONDS_WELL_TO
- No relational tables — all state lives on graph edges
- 8 tools: query_concepts, ingest_evidence, get_learner_state, get_learner_profile, get_confusion_pairs, get_effective_contexts, plan_session, replan_activity
- Curriculum planner: stateless priority scoring (decay urgency + readiness + confusion opportunity) → SessionPlan with ordered activities
- Every connection requires `LOAD 'age'` — handled by pool configure callback

**Webapp**: Next.js 15 with App Router
- Tabbed UI: Practice (session lifecycle + continuous voice streaming) | Progress (learner dashboard)
- AudioWorklet captures mic → PCM int16 chunks sent immediately via WebSocket (continuous streaming)
- Mute/unmute toggle replaces press-to-talk (Smart Turn handles turn detection server-side)
- Session modes: structured (plan_session → activity transitions) or free conversation
- Hooks: `useSession` (lifecycle), `useVoiceAgent` (WebSocket + continuous streaming + mute), `useLearnerProfile`, `useLearnerState`
- Health check polling at `/health` with warmup detection (503 → pulsing yellow indicator)

## External Dependencies

- **llama-server**: runs via Docker (see `docker-compose.yml`), serves GGUF model on `:8081`
- **GGUF model**: download `Llama-3.2-3B-Instruct-Q8_0.gguf` into `models/` at repo root
- Piper TTS model expected at: `~/piper_models/es_ES-carlfm-x_low.onnx` (loaded directly by PiperTTSService, no CLI needed)
- GPU with VRAM for llama-server voice (~3.5GB for Q8_0 3B) + llama-server judge (~5.5GB for Q4_K_M 8B) + Whisper (~1GB)

## WebSocket Protocol

**Endpoint:** `ws://localhost:8765/ws/voice`

1. On connect: server sends `session_plan` JSON if structured mode active.
2. Client streams raw `int16` PCM chunks continuously (16 kHz mono). Smart Turn detects turn boundaries server-side.
3. Server replies with N+1 messages per turn:
   - N binary frames: synthesized audio sentences (int16, 16 kHz, mono) — streamed as LLM generates
   - 1 text frame: JSON `{ type: "metrics", data: { stt_ms, llm_ms, tts_ms, total_ms }, transcription, response }` (sent after all TTS audio)
4. Between activities (structured mode), server may send:
   - `{ type: "activity_change", activity_index, activity, replan_action, replan_reason, remaining_activities }`
   - `{ type: "session_end", session_id, reason }`

**Health check:** `GET /health` — returns 503 `{"status": "warming_up"}` during startup, 200 `{"status": "ok"}` when ready

## Key Files

- `voice-agent/voice_agent_pipecat.py`: Production Pipecat server with REST + WebSocket pipeline
- `voice-agent/comprende_serializer.py`: Custom FrameSerializer bridging webapp protocol with Pipecat frames
- `voice-agent/session_interceptor.py`: TranscriptionObserver + SessionInterceptor FrameProcessors
- `voice-agent/session_manager.py`: Session lifecycle (structured/free), activity transitions, assessment firing
- `voice-agent/mcp_client.py`: MCP client wrapper (plan_session, assess_interaction, learner queries)
- `voice-agent/voice_agent_server.py`: Legacy manual STT→LLM→TTS server (preserved as fallback)
- `voice-agent/test_client.py`: Interactive microphone test client
- `voice-agent/benchmark.py`: Latency benchmarking tool
- `voice-agent/diagnostic.py`: Component-level diagnostic
- `webapp/hooks/useVoiceAgent.ts`: WebSocket + continuous audio streaming hook (startStreaming/stopStreaming/toggleMute)
- `webapp/hooks/useSession.ts`: Session lifecycle hook (start/end, mode, activity tracking)
- `webapp/hooks/useLearnerProfile.ts`: Learner profile polling hook
- `webapp/hooks/useLearnerState.ts`: On-demand learner state + confusions + contexts
- `webapp/hooks/useHealthCheck.ts`: Health polling hook (detects warmup state)
- `webapp/lib/voice-protocol.ts`: Protocol TypeScript types (metrics, session plan, activity, learner data)
- `webapp/lib/constants.ts`: Voice agent URLs & audio constants
- `webapp/components/PracticeView.tsx`: Session controls + mute/unmute + conversation display
- `webapp/components/ProgressView.tsx`: Learner dashboard with mastery bars and confusion pairs
- `webapp/components/ActivityCard.tsx`: Current activity display with timer
- `webapp/components/ConversationTurn.tsx`: Single turn display with metrics
- `webapp/components/ConceptCard.tsx`: Concept mastery bar with trend
- `webapp/components/ConfusionPairCard.tsx`: Confusion pair display
- `webapp/components/HealthIndicator.tsx`: Connection status indicator (green/yellow/red)
- `comprende-ya-mcp/mcp_server/server.py`: FastMCP server with tool registration + lifespan
- `comprende-ya-mcp/mcp_server/db.py`: Async pool, cypher_query() helper
- `comprende-ya-mcp/mcp_server/graph_schema.py`: AGE graph schema initialization + drop_graph helper
- `comprende-ya-mcp/mcp_server/b2_seed.py`: B2 concept graph seeder (reads concept_graph.json)
- `comprende-ya-mcp/mcp_server/seed.py`: Legacy A1 YAML curriculum seeder
- `comprende-ya-mcp/mcp_server/learner_model.py`: Pure learner model logic (half-life decay, EMA mastery, trend, confidence, confusion detection)
- `comprende-ya-mcp/mcp_server/tools/concepts.py`: query_concepts tool (browse concept graph)
- `comprende-ya-mcp/mcp_server/tools/ingest_evidence.py`: ingest_evidence tool (batch write evidence, recompute STUDIES)
- `comprende-ya-mcp/mcp_server/tools/learner_state.py`: get_learner_state tool (STUDIES edges with decay projection)
- `comprende-ya-mcp/mcp_server/tools/learner.py`: get_learner_profile tool (mastered/progressing/decaying/unseen)
- `comprende-ya-mcp/mcp_server/tools/confusion_pairs.py`: get_confusion_pairs tool (CONFUSES_WITH edges)
- `comprende-ya-mcp/mcp_server/tools/effective_contexts.py`: get_effective_contexts tool (RESPONDS_WELL_TO edges)
- `comprende-ya-mcp/mcp_server/planner.py`: Pure curriculum planner logic (scoring, plan assembly, replanning)
- `comprende-ya-mcp/mcp_server/tools/planner.py`: MCP tool wrappers for plan_session, replan_activity
- `concept_graph.json`: B2 concept taxonomy (53 concepts, source of truth)
- `voice-agent/mcp_client.py`: MCP client wrapper for voice agent
- `NEXT_STEPS.md`: Development roadmap / TODO checklist
