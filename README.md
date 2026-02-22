# Comprende Ya

Spanish learning app powered by local AI. Real-time voice conversation with a **STT → LLM → TTS** pipeline, all running on-device.

## Monorepo Structure

```
comprende-ya/
├── voice-agent/        # Python voice pipeline (Whisper + Llama + Piper)
├── webapp/             # Next.js web client
├── shared/             # Shared TypeScript types & constants
├── comprende-ya-mcp/   # Knowledge graph MCP server (FastMCP + PostgreSQL/AGE)
├── pyproject.toml      # Root uv workspace
└── docker-compose.yml  # (Phase 4)
```

## Features

- **Fully local** — no cloud API calls; all inference runs on your GPU
- **Low latency** — optimized for sub-second turn-around
- **Browser UI** — record audio, see transcription + response, view latency metrics
- **WebSocket API** — stream raw audio in, get audio + JSON metrics back

## Architecture

```
Browser ──► WebSocket ──► Faster-Whisper (STT)
                                │
                                ▼
                          Llama 3.2-3B (LLM)
                                │
                                ▼
                          Piper TTS ──► Browser
```

| Component | Model / Tool | Details |
|-----------|-------------|---------|
| **STT** | Faster-Whisper (`small`) | CUDA, float16, VAD filter, beam size 5 |
| **LLM** | `meta-llama/Llama-3.2-3B-Instruct` via vLLM | half precision, 512-token context |
| **TTS** | Piper (`es_ES-carlfm-x_low`) | CLI subprocess |
| **Server** | FastAPI + Uvicorn | WebSocket at `/ws/voice`, health at `/health` |
| **Client** | Next.js 15 + AudioWorklet | PCM int16 capture via AudioWorklet |

## Requirements

- Python 3.12+
- Node.js 22+ with pnpm
- NVIDIA GPU with **10 GB+ VRAM**
- [uv](https://docs.astral.sh/uv/) package manager
- `piper` CLI installed and on PATH
- Piper voice model at `~/piper_models/es_ES-carlfm-x_low.onnx`

## Setup

```bash
# Install Python deps (from repo root)
uv sync --all-packages

# Install webapp deps
cd webapp && pnpm install
```

## Usage

### Start the voice agent

```bash
uv run --package voice-agent python voice-agent/voice_agent_server.py
```

Starts on `0.0.0.0:8765`. Models load at startup (vLLM first, then Whisper).

### Start the web client

```bash
cd webapp && pnpm dev
```

Opens on `http://localhost:3000`. Shows a health indicator (green when voice agent is running). Click the record button to capture audio and send it to the voice agent.

### Start the judge LLM (for assessment)

The assessment layer uses a separate vLLM instance as an LLM-as-judge to score learner utterances against concept mastery signals.

```bash
vllm serve meta-llama/Llama-3.2-3B-Instruct \
  --port 8002 \
  --gpu-memory-utilization 0.4 \
  --max-model-len 4096 \
  --dtype half
```

Listens on `http://localhost:8002` (OpenAI-compatible API). Configure via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `JUDGE_LLM_BASE_URL` | `http://localhost:8002/v1` | Base URL for the judge LLM API |
| `JUDGE_LLM_MODEL` | `meta-llama/Llama-3.2-3B-Instruct` | Model name sent in requests |
| `JUDGE_LLM_TIMEOUT` | `30.0` | Request timeout in seconds |

> **Note:** If you're already running vLLM for the voice agent on port 8765, the judge needs its own instance on a separate port. Adjust `--gpu-memory-utilization` so both fit in VRAM.

### CLI tools

```bash
# Test with microphone
uv run --package voice-agent python voice-agent/test_client.py

# Benchmark latency
uv run --package voice-agent python voice-agent/benchmark.py

# Run diagnostics
uv run --package voice-agent python voice-agent/diagnostic.py
```

## WebSocket Protocol

**Endpoint:** `ws://localhost:8765/ws/voice`

1. Client sends raw `int16` audio bytes (16 kHz, mono).
2. Server replies with:
   - **Binary frame** — synthesized audio (int16, 16 kHz, mono)
   - **Text frame** — JSON metrics:
     ```json
     {
       "type": "metrics",
       "data": { "stt_ms": 120.5, "llm_ms": 85.3, "tts_ms": 200.1, "total_ms": 406.2 },
       "transcription": "Hola, ¿cómo estás?",
       "response": "¡Muy bien, gracias!"
     }
     ```

**Health check:** `GET /health` → `{"status": "ok", "gpu": "<device name>"}`

## Important: Model Loading Order

vLLM **must** be loaded before Faster-Whisper. vLLM spawns child processes that need CUDA initialization before any CUDA context exists in the parent process.

## Next Steps

See [NEXT_STEPS.md](NEXT_STEPS.md) for the development roadmap.

## License

MIT
