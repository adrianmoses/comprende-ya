# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spanish learning app powered by local AI. Monorepo with a voice agent (Python), web client (Next.js), and MCP server (placeholder).

## Monorepo Structure

```
comprende-ya/
├── voice-agent/        # STT → LLM → TTS pipeline (Python/uv)
├── webapp/             # Next.js web client (pnpm)
├── mcp-server/         # Knowledge graph server (Phase 2, placeholder)
├── pyproject.toml      # Root uv workspace
└── docker-compose.yml  # Placeholder for Phase 4
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
```

## Architecture

**Voice pipeline**: Audio bytes → STT → LLM → TTS → Audio response

- **STT**: Faster-Whisper (`small` model, CUDA, float16)
- **LLM**: vLLM with `meta-llama/Llama-3.2-3B-Instruct` (half precision, 512 token context)
- **TTS**: Piper via CLI subprocess (Spanish voice model)

**Server**: FastAPI with WebSocket endpoint at `/ws/voice`
- Receives: raw int16 audio bytes (16kHz mono)
- Returns: audio bytes + JSON metrics (transcription, response, latencies)

**Webapp**: Next.js 15 with App Router
- AudioWorklet captures mic → PCM int16 via WebSocket
- Health check polling at `/health`

## Critical: Model Loading Order

vLLM **must** be loaded before Faster-Whisper. vLLM spawns subprocesses that require CUDA initialization before any CUDA context exists in the parent process. Loading Whisper first will cause CUDA errors in vLLM's subprocess.

## External Dependencies

- Piper TTS model expected at: `~/piper_models/es_ES-carlfm-x_low.onnx`
- `piper` command must be in PATH
- GPU with ~10GB+ VRAM (Llama 3.2-3B uses ~6GB, Whisper uses additional memory)

## WebSocket Protocol

**Endpoint:** `ws://localhost:8765/ws/voice`

1. Client sends raw `int16` audio bytes (16 kHz mono).
2. Server replies with two messages:
   - Binary frame: synthesized audio (int16, 16 kHz, mono)
   - Text frame: JSON `{ type, data: { stt_ms, llm_ms, tts_ms, total_ms }, transcription, response }`

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
- `NEXT_STEPS.md`: Development roadmap / TODO checklist
