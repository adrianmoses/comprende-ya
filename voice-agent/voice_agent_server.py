import asyncio
import logging
import os
import re


def _ensure_nvidia_lib_path() -> None:
    """Add pip-installed NVIDIA lib dirs to LD_LIBRARY_PATH and re-exec if needed.

    ctranslate2 (used by faster-whisper) loads libcublas via dlopen, which reads
    LD_LIBRARY_PATH at process startup.  Pip-installed nvidia-cublas-cu12 places
    the .so in a site-packages subdir that isn't on the default search path.
    """
    try:
        import nvidia.cublas.lib
        import nvidia.cudnn.lib
    except ImportError:
        return  # system CUDA install — no pip nvidia packages

    dirs = []
    for mod in (nvidia.cublas.lib, nvidia.cudnn.lib):
        # These are namespace packages so __file__ is None; use __path__ instead
        paths = getattr(mod, "__path__", None)
        d = (
            str(paths[0])
            if paths
            else (os.path.dirname(mod.__file__) if mod.__file__ else None)
        )
        if d and d not in os.environ.get("LD_LIBRARY_PATH", ""):
            dirs.append(d)

    if not dirs:
        return  # already on path

    existing = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = ":".join(dirs + ([existing] if existing else []))
    # Re-exec so the dynamic linker sees the updated path
    import sys

    os.execv(sys.executable, [sys.executable] + sys.argv)


_ensure_nvidia_lib_path()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
import numpy as np  # noqa: E402
import json  # noqa: E402
from datetime import datetime  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402

import mcp_client  # noqa: E402
from session_manager import SessionManager  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# LOAD MODELS / CLIENTS
# ============================================

logger.info("Loading models...")

# Whisper STT
logger.info("  - Loading Whisper...")
whisper_model = WhisperModel(
    "small",
    device="cuda",
    compute_type="float16",
)
logger.info("  Whisper loaded")
logger.info(os.getenv("LD_LIBRARY_PATH", ""))

# LLM via llama-server (OpenAI-compatible API)
LLAMA_SERVER_URL = os.getenv("LLAMA_SERVER_URL", "http://localhost:8081/v1")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "Llama-3.2-3B-Instruct-Q8_0.gguf")
llm_client = AsyncOpenAI(base_url=LLAMA_SERVER_URL, api_key="not-needed")
logger.info(f"  LLM client: {LLAMA_SERVER_URL}")

# Piper TTS
PIPER_MODEL_PATH = os.path.expanduser("~/piper_models/es_ES-carlfm-x_low.onnx")
logger.info(f"  Piper TTS: {PIPER_MODEL_PATH}")
logger.info("All models/clients ready!")


# ============================================
# FUNCTIONS
# ============================================

SENTENCE_ENDINGS = re.compile(r"[.!?](?:\s+|$)")

LEARNER_ID = os.getenv("LEARNER_ID", "default_learner")

# Global session manager (one per server instance — single learner for now)
session_manager = SessionManager(LEARNER_ID)


async def transcribe_audio(audio_bytes):
    """STT with timeout"""
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    def _transcribe():
        segments, info = whisper_model.transcribe(
            audio_np,
            language="es",
            beam_size=5,
            vad_filter=True,
            temperature=0.0,
            initial_prompt="Hola, ¿cómo estás? Soy un asistente de español.",
        )
        return " ".join([segment.text for segment in segments]).strip()

    return await asyncio.to_thread(_transcribe)


async def text_to_speech(text):
    """TTS with fallback"""

    if not text or len(text) < 2:
        return np.zeros(8000, dtype=np.int16).tobytes()

    text = text[:200]  # Limit length

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        process = await asyncio.create_subprocess_exec(
            "piper",
            "--model",
            PIPER_MODEL_PATH,
            "--output_file",
            tmp_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=text.encode("utf-8")),
            timeout=5.0,
        )

        if process.returncode != 0:
            raise Exception(f"Piper error: {stderr.decode()}")

        import wave

        with wave.open(tmp_path, "rb") as wf:
            audio_data = wf.readframes(wf.getnframes())

        return audio_data

    except Exception as e:
        logger.error(f"TTS error: {e}")
        t = np.linspace(0, 0.3, 4800)
        beep = (np.sin(2 * np.pi * 440 * t) * 8000).astype(np.int16)
        return beep.tobytes()

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def stream_and_speak(websocket, user_text, system_prompt):
    """Stream LLM tokens, buffer by sentence, flush each sentence to TTS.

    Returns (full_response, llm_seconds, tts_seconds).
    """
    buffer = ""
    full_response = ""
    tts_total = 0.0

    llm_start = datetime.now()
    stream = await llm_client.chat.completions.create(
        model=LLAMA_MODEL,
        stream=True,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0.7,
        top_p=0.9,
        max_tokens=60,
        stop=["\n\n"],
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta
        token = delta.content if delta.content else ""
        buffer += token
        full_response += token

        # Flush on sentence boundary
        if SENTENCE_ENDINGS.search(buffer):
            sentence = buffer.strip()
            buffer = ""
            if sentence:
                tts_start = datetime.now()
                audio = await text_to_speech(sentence)
                tts_total += (datetime.now() - tts_start).total_seconds()
                await websocket.send_bytes(audio)

    llm_seconds = (datetime.now() - llm_start).total_seconds() - tts_total

    # Flush remaining buffer
    if buffer.strip():
        tts_start = datetime.now()
        audio = await text_to_speech(buffer.strip())
        tts_total += (datetime.now() - tts_start).total_seconds()
        await websocket.send_bytes(audio)

    return full_response.strip(), llm_seconds, tts_total


# ============================================
# REST ENDPOINTS
# ============================================


@app.post("/session/start")
async def start_session(body: dict | None = None):
    """Start a new learning session.

    Body: {mode?: "structured"|"free", duration_min?: number}
    """
    body = body or {}
    mode = body.get("mode", "structured")
    duration_min = body.get("duration_min", 30.0)

    if mode == "structured":
        plan = await session_manager.start_structured_session(duration_min)
        return {"status": "ok", "plan": plan}
    else:
        result = session_manager.start_free_session()
        return {"status": "ok", "plan": result}


@app.post("/session/end")
async def end_session():
    """End the current session."""
    summary = await session_manager.end_session()
    return {"status": "ok", "summary": summary}


@app.get("/session/state")
async def get_session_state():
    """Get current session state."""
    info = session_manager.get_session_info()
    if not info:
        return {"status": "no_session"}
    return {"status": "ok", **info}


@app.get("/learner/profile")
async def get_learner_profile():
    """Proxy to MCP get_learner_profile."""
    profile = await mcp_client.get_learner_profile(LEARNER_ID)
    return profile


@app.get("/learner/state")
async def get_learner_state(concept_ids: str | None = None):
    """Proxy to MCP get_learner_state.

    Query param concept_ids: comma-separated concept IDs (optional).
    """
    ids = concept_ids.split(",") if concept_ids else None
    states = await mcp_client.get_learner_state(LEARNER_ID, concept_ids=ids)
    return states


@app.get("/learner/confusions")
async def get_learner_confusions():
    """Proxy to MCP get_confusion_pairs."""
    pairs = await mcp_client.get_confusion_pairs(LEARNER_ID)
    return pairs


@app.get("/learner/contexts")
async def get_learner_contexts():
    """Proxy to MCP get_effective_contexts."""
    contexts = await mcp_client.get_effective_contexts(LEARNER_ID)
    return contexts


# ============================================
# WEBSOCKET
# ============================================


class Metrics:
    def __init__(self):
        self.reset()

    def reset(self):
        self.stt_time = 0
        self.llm_time = 0
        self.tts_time = 0
        self.total_time = 0

    def to_dict(self):
        return {
            "stt_ms": round(self.stt_time * 1000, 2),
            "llm_ms": round(self.llm_time * 1000, 2),
            "tts_ms": round(self.tts_time * 1000, 2),
            "total_ms": round(self.total_time * 1000, 2),
        }


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected")

    sm = session_manager

    # If no active session, start free mode
    if not sm.state:
        sm.start_free_session()

    # Send session_plan message if structured mode
    if sm.state and sm.state.mode == "structured" and sm.state.plan:
        await websocket.send_text(
            json.dumps({"type": "session_plan", "plan": sm.state.plan})
        )

    system_prompt = sm.get_system_prompt()

    try:
        while True:
            data = await websocket.receive_bytes()
            logger.info(f"Received {len(data)} bytes")

            metrics = Metrics()
            start = datetime.now()

            # STT
            stt_start = datetime.now()
            transcription = await transcribe_audio(data)
            metrics.stt_time = (datetime.now() - stt_start).total_seconds()
            logger.info(f"STT: '{transcription}' ({metrics.stt_time * 1000:.0f}ms)")

            if not transcription:
                logger.warning("No transcription")
                await websocket.send_bytes(np.zeros(8000, dtype=np.int16).tobytes())
                metrics.total_time = (datetime.now() - start).total_seconds()
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "metrics",
                            "data": metrics.to_dict(),
                            "transcription": "",
                            "response": "",
                        }
                    )
                )
                continue

            # Record learner turn
            sm.record_turn("learner", transcription)

            # Refresh system prompt (may change after activity transition)
            system_prompt = sm.get_system_prompt()

            # LLM streaming + TTS (sentence-level flushing)
            response_text, llm_seconds, tts_seconds = await stream_and_speak(
                websocket, transcription, system_prompt
            )
            metrics.llm_time = llm_seconds
            metrics.tts_time = tts_seconds
            logger.info(
                f"LLM: '{response_text}' ({metrics.llm_time * 1000:.0f}ms), "
                f"TTS: ({metrics.tts_time * 1000:.0f}ms)"
            )

            # Record teacher turn
            sm.record_turn("teacher", response_text)

            metrics.total_time = (datetime.now() - start).total_seconds()

            # Send metrics JSON after all audio chunks
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "metrics",
                        "data": metrics.to_dict(),
                        "transcription": transcription,
                        "response": response_text,
                    }
                )
            )

            logger.info(f"TOTAL: {metrics.total_time * 1000:.0f}ms\n" + "=" * 60)

            # Check for activity transition (structured mode only)
            if sm.should_check_activity():
                logger.info("Activity duration elapsed — checking transition")
                transition = await sm.check_and_transition()
                if transition:
                    await websocket.send_text(json.dumps(transition))
                    logger.info(f"Sent transition: {transition.get('type')}")

    except WebSocketDisconnect:
        logger.info("Client disconnected")
        # Fire final assessment for remaining buffered turns
        if sm.state and sm.state.turn_buffer:
            await sm.end_session()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


@app.get("/health")
async def health():
    return {"status": "ok", "llm_backend": LLAMA_SERVER_URL}


async def warmup():
    """Warm up all models to avoid cold-start latency."""
    logger.info("Warming up models...")

    # STT warmup
    dummy_audio = np.zeros(16000, dtype=np.float32)  # 1s silence
    whisper_model.transcribe(dummy_audio, language="es")
    logger.info("  STT warm")

    # LLM warmup — retry until llama-server is reachable
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            await llm_client.chat.completions.create(
                model=LLAMA_MODEL,
                messages=[{"role": "user", "content": "Hola"}],
                max_tokens=1,
            )
            logger.info("  LLM warm")
            break
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"  LLM warmup failed after {max_retries} attempts: {e}")
                raise
            logger.info(
                f"  LLM not ready (attempt {attempt}/{max_retries}), retrying in 3s..."
            )
            await asyncio.sleep(3)

    # TTS warmup
    subprocess.run(
        ["piper", "--model", PIPER_MODEL_PATH, "--output_file", "/dev/null"],
        input=b"Hola",
        capture_output=True,
        timeout=10,
    )
    logger.info("  TTS warm")

    logger.info("Warmup complete!")


if __name__ == "__main__":
    import uvicorn

    asyncio.run(warmup())
    uvicorn.run(app, host="0.0.0.0", port=8765)
