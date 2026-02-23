# Comprende Ya

Spanish learning app powered by local AI. Voice agent with STT/LLM/TTS pipeline, knowledge graph curriculum planner, and web client — all running on-device.

## Quick Start (Docker)

### Prerequisites

- Docker with Compose v2
- NVIDIA GPU with [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- ~10GB VRAM (3.5GB voice LLM + 5.5GB judge LLM + 1GB Whisper)

### 1. Download models

**GGUF models** — place in `models/`:

```bash
# Voice LLM (3B, Q8_0)
huggingface-cli download bartowski/Llama-3.2-3B-Instruct-GGUF \
  Llama-3.2-3B-Instruct-Q8_0.gguf --local-dir models/

# Judge LLM (8B, Q4_K_M)
huggingface-cli download bartowski/Meta-Llama-3.1-8B-Instruct-GGUF \
  Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf --local-dir models/
```

**Piper TTS model** — place in `models/piper/`:

```bash
mkdir -p models/piper
wget -P models/piper/ \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx.json
```

### 2. Start everything

```bash
docker compose up -d
```

This starts all 6 services:

| Service | Port | Description |
|---------|------|-------------|
| `age` | 5455 | PostgreSQL + Apache AGE (knowledge graph) |
| `llama-server` | 8081 | Voice LLM (Llama 3.2-3B, Q8_0) |
| `llama-server-judge` | 8082 | Assessment judge LLM (Llama 3.1-8B, Q4_K_M) |
| `mcp-server` | 8001 | MCP server (curriculum + learner model) |
| `voice-agent` | 8765 | Voice pipeline (Whisper STT → LLM → Piper TTS) |
| `webapp` | 3000 | Next.js web client |

### 3. Seed the concept graph (first run only)

```bash
docker compose exec mcp-server python -m mcp_server.b2_seed
```

### 4. Open the app

Navigate to [http://localhost:3000](http://localhost:3000).

### Verify

```bash
docker compose ps              # All services healthy
curl http://localhost:8765/health  # Voice agent
curl http://localhost:8001/        # MCP server
```

## Configuration

Copy `.env.example` to `.env` to customize. Available options:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLAMA_MODEL` | `Llama-3.2-3B-Instruct-Q8_0.gguf` | Voice LLM model file |
| `JUDGE_MODEL` | `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` | Judge LLM model file |
| `LEARNER_ID` | `default_learner` | Learner identifier |

## Architecture

```
Browser ←→ Webapp (Next.js :3000)
              ↓
Voice Agent (FastAPI :8765)
  ├── Whisper STT (CUDA)
  ├── llama-server (3B LLM :8081)
  ├── Piper TTS
  └── MCP Server (FastMCP :8001)
        ├── AGE Graph DB (:5455)
        └── llama-server Judge (8B LLM :8082)
```

## Monorepo Structure

```
comprende-ya/
├── voice-agent/        # STT → LLM → TTS pipeline (Python/uv)
├── webapp/             # Next.js web client (pnpm)
├── comprende-ya-mcp/   # Knowledge graph MCP server (FastMCP + PostgreSQL/AGE)
├── models/             # GGUF + Piper model files (gitignored)
├── pyproject.toml      # Root uv workspace
└── docker-compose.yml  # Full stack orchestration
```

## Local Development (without Docker)

See [CLAUDE.md](CLAUDE.md) for individual service commands.

```bash
# Install Python deps
uv sync --all-packages

# Install webapp deps
cd webapp && pnpm install

# Start infrastructure only
docker compose up -d age llama-server llama-server-judge

# Start services manually
uv run --package comprende-ya-mcp python -m mcp_server.server
uv run --package voice-agent python voice-agent/voice_agent_server.py
cd webapp && pnpm dev
```

## WebSocket Protocol

**Endpoint:** `ws://localhost:8765/ws/voice`

1. Client sends raw `int16` audio bytes (16 kHz, mono).
2. Server replies with N binary frames (audio sentences) + 1 JSON metrics frame.
3. Structured mode sends additional `activity_change` and `session_end` messages.

See [CLAUDE.md](CLAUDE.md) for full protocol details.

## Next Steps

See [NEXT_STEPS.md](NEXT_STEPS.md) for the development roadmap.

## License

MIT
