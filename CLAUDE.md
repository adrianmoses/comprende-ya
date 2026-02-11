# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spanish voice agent using local AI models for real-time voice conversation. Processes audio through a STT → LLM → TTS pipeline via WebSocket.

## Commands

```bash
# Run the main server (starts on port 8765)
uv run voice_agent_server.py

# Test with microphone input
uv run test_client.py

# Run performance benchmark
uv run benchmark.py

# Run component diagnostics (mic, STT, TTS)
uv run diagnostic.py
```

## Architecture

**Pipeline flow**: Audio bytes → STT → LLM → TTS → Audio response

- **STT**: Faster-Whisper (`small` model, CUDA, float16)
- **LLM**: vLLM with `meta-llama/Llama-3.2-3B-Instruct` (half precision, 512 token context)
- **TTS**: Piper via CLI subprocess (Spanish voice model)

**Server**: FastAPI with WebSocket endpoint at `/ws/voice`
- Receives: raw int16 audio bytes (16kHz mono)
- Returns: audio bytes + JSON metrics (transcription, response, latencies)

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

- `voice_agent_server.py`: Production server with real models
- `voice_agent_local.py`: Pipecat-based pipeline with mock services (for testing pipeline structure)
- `test_client.py`: Interactive microphone test client
- `benchmark.py`: Latency benchmarking tool (generates `benchmark_results.png`)
- `diagnostic.py`: Component-level diagnostic (mic capture, Whisper, Piper)
- `NEXT_STEPS.md`: Development roadmap / TODO checklist
