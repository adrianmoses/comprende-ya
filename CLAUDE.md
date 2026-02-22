# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spanish learning app powered by local AI. Monorepo with a voice agent (Python), web client (Next.js), and MCP server (knowledge graph + curriculum).

## Monorepo Structure

```
comprende-ya/
├── voice-agent/        # STT → LLM → TTS pipeline (Python/uv)
├── webapp/             # Next.js web client (pnpm)
├── comprende-ya-mcp/         # Knowledge graph MCP server (FastMCP + PostgreSQL/AGE)
├── pyproject.toml      # Root uv workspace
├── models/             # GGUF model files for llama-server
└── docker-compose.yml  # PostgreSQL + AGE (5455) + llama-server (8081)
```

## Commands

```bash
# Python workspace (from repo root)
uv sync --all-packages                           # Install all Python deps
uv run --package voice-agent python voice-agent/voice_agent_server.py  # Start voice agent
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

**Voice pipeline**: Audio bytes → STT → LLM (streaming) → TTS (sentence-level) → Audio response

- **STT**: Faster-Whisper (`small` model, CUDA, float16)
- **LLM**: llama-server (`Llama-3.2-3B-Instruct` GGUF Q8_0) via OpenAI-compatible API on `:8081`
- **TTS**: Piper via CLI subprocess (Spanish voice model)
- Both voice agent and MCP judge share the same llama-server instance

**Server**: FastAPI with WebSocket endpoint at `/ws/voice`
- Receives: raw int16 audio bytes (16kHz mono)
- Returns: N binary frames (one per sentence, streamed) + 1 JSON metrics text frame

**MCP Server**: FastMCP with PostgreSQL + Apache AGE (Cypher graph queries)
- Concept graph: 53 B2-level Concept nodes with REQUIRES (DAG), RELATED_TO, CONTRASTS_WITH edges
- Context nodes: label created, population deferred to Phase 3C
- Learner model: STUDIES edges (half-life decay mastery), EVIDENCE edges (immutable event log), CONFUSES_WITH, RESPONDS_WELL_TO
- No relational tables — all state lives on graph edges
- 8 tools: query_concepts, ingest_evidence, get_learner_state, get_learner_profile, get_confusion_pairs, get_effective_contexts, plan_session, replan_activity
- Curriculum planner: stateless priority scoring (decay urgency + readiness + confusion opportunity) → SessionPlan with ordered activities
- Every connection requires `LOAD 'age'` — handled by pool configure callback

**Webapp**: Next.js 15 with App Router
- AudioWorklet captures mic → PCM int16 via WebSocket
- Health check polling at `/health`

## External Dependencies

- **llama-server**: runs via Docker (see `docker-compose.yml`), serves GGUF model on `:8081`
- **GGUF model**: download `Llama-3.2-3B-Instruct-Q8_0.gguf` into `models/` at repo root
- Piper TTS model expected at: `~/piper_models/es_ES-carlfm-x_low.onnx`
- `piper` command must be in PATH
- GPU with VRAM for llama-server (~4GB for Q8_0 3B) + Whisper

## WebSocket Protocol

**Endpoint:** `ws://localhost:8765/ws/voice`

1. Client sends raw `int16` audio bytes (16 kHz mono).
2. Server replies with N+1 messages:
   - N binary frames: synthesized audio sentences (int16, 16 kHz, mono) — streamed as LLM generates
   - 1 text frame: JSON `{ type, data: { stt_ms, llm_ms, tts_ms, total_ms }, transcription, response }`

**Health check:** `GET /health`

## Key Files

- `voice-agent/voice_agent_server.py`: Production server with real models
- `voice-agent/voice_agent_local.py`: Pipecat-based pipeline with mock services
- `voice-agent/test_client.py`: Interactive microphone test client
- `voice-agent/benchmark.py`: Latency benchmarking tool
- `voice-agent/diagnostic.py`: Component-level diagnostic
- `webapp/hooks/useVoiceAgent.ts`: WebSocket + audio capture hook
- `webapp/hooks/useHealthCheck.ts`: Health polling hook
- `webapp/lib/voice-protocol.ts`: Protocol TypeScript types
- `webapp/lib/constants.ts`: Voice agent URLs & audio constants
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
