# es-voice-agent

Real-time Spanish voice conversation agent powered by local AI models. Speaks and listens entirely on-device using a **STT → LLM → TTS** pipeline over WebSocket.

## Features

- **Fully local** — no cloud API calls; all inference runs on your GPU
- **Low latency** — optimized for sub-second turn-around (short context, small models)
- **WebSocket API** — stream raw audio in, get audio + JSON metrics back
- **Spanish-first** — Whisper tuned for `es`, Piper Spanish voice, LLM system prompt in Spanish

## Architecture

```
Microphone ──► WebSocket ──► Faster-Whisper (STT)
                                    │
                                    ▼
                              Llama 3.2-3B (LLM)
                                    │
                                    ▼
                              Piper TTS ──► Speaker
```

| Component | Model / Tool | Details |
|-----------|-------------|---------|
| **STT** | Faster-Whisper (`base`) | CUDA, float16, VAD filter, beam size 3 |
| **LLM** | `meta-llama/Llama-3.2-3B-Instruct` via vLLM | half precision, 512-token context, 30-token max output |
| **TTS** | Piper (`es_ES-sharvard-medium`) | CLI subprocess, WAV output |
| **Server** | FastAPI + Uvicorn | WebSocket at `/ws/voice`, health check at `/health` |

Audio format: **16 kHz, mono, int16** (both input and output).

## Requirements

- Python 3.13+
- NVIDIA GPU with **10 GB+ VRAM** (Llama 3.2-3B ~6 GB, Whisper uses the rest)
- [uv](https://docs.astral.sh/uv/) package manager
- `piper` CLI installed and on PATH
- Piper voice model at `~/piper_models/es_ES-sharvard-medium.onnx`

## Setup

```bash
# Clone the repo
git clone https://github.com/<your-user>/es-voice-agent.git
cd es-voice-agent

# Install dependencies (uv reads pyproject.toml)
uv sync

# Download the Piper Spanish voice model
mkdir -p ~/piper_models
# Place es_ES-sharvard-medium.onnx and its .json config in ~/piper_models/
```

## Usage

### Start the server

```bash
uv run voice_agent_server.py
```

The server starts on `0.0.0.0:8765`. Models are loaded at startup (vLLM first, then Whisper — order matters; see below).

### Test with your microphone

```bash
uv run test_client.py
```

Records 3 seconds of audio, sends it to the server, prints the transcription and response, and plays back the generated speech.

### Run the benchmark

```bash
uv run benchmark.py
```

Sends 20 silent-audio requests and reports per-component latency statistics. Saves a histogram chart to `benchmark_results.png`.

### Run diagnostics

```bash
uv run diagnostic.py
```

Step-by-step check of microphone capture, Whisper transcription, and Piper TTS. Useful for debugging hardware or model issues.

## WebSocket Protocol

**Endpoint:** `ws://localhost:8765/ws/voice`

1. Client sends raw `int16` audio bytes (16 kHz, mono).
2. Server replies with two messages:
   - **Binary frame** — synthesized audio response (int16, 16 kHz, mono)
   - **Text frame** — JSON with metrics:
     ```json
     {
       "type": "metrics",
       "data": {
         "stt_ms": 120.5,
         "llm_ms": 85.3,
         "tts_ms": 200.1,
         "total_ms": 406.2
       },
       "transcription": "Hola, ¿cómo estás?",
       "response": "¡Muy bien, gracias!"
     }
     ```

**Health check:** `GET /health` — returns `{"status": "ok", "gpu": "<device name>"}`.

## Project Structure

```
es-voice-agent/
├── voice_agent_server.py   # Production server (real models)
├── voice_agent_local.py    # Pipecat-based pipeline with mock services
├── test_client.py          # Interactive microphone test client
├── benchmark.py            # Latency benchmark (generates benchmark_results.png)
├── diagnostic.py           # Component-level diagnostic script
├── pyproject.toml          # Project metadata and dependencies
├── CLAUDE.md               # AI assistant instructions
└── NEXT_STEPS.md           # Development roadmap
```

## Important: Model Loading Order

vLLM **must** be loaded before Faster-Whisper. vLLM spawns child processes that need CUDA initialization before any CUDA context exists in the parent process. Loading Whisper first will cause CUDA errors in vLLM's subprocess.

## Next Steps

See [NEXT_STEPS.md](NEXT_STEPS.md) for the development roadmap.

## License

MIT
