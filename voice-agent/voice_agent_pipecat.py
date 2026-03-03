"""Pipecat-based voice agent server with Smart Turn detection.

Replaces the manual STT→LLM→TTS loop with Pipecat's pipeline architecture,
enabling continuous audio streaming and natural turn-taking.
"""

import asyncio
import json
import logging
import os
from pathlib import Path


def _ensure_nvidia_lib_path() -> None:
    """Add pip-installed NVIDIA lib dirs to LD_LIBRARY_PATH and re-exec if needed."""
    try:
        import nvidia.cublas.lib
        import nvidia.cudnn.lib
    except ImportError:
        return

    dirs = []
    for mod in (nvidia.cublas.lib, nvidia.cudnn.lib):
        paths = getattr(mod, "__path__", None)
        d = (
            str(paths[0])
            if paths
            else (os.path.dirname(mod.__file__) if mod.__file__ else None)
        )
        if d and d not in os.environ.get("LD_LIBRARY_PATH", ""):
            dirs.append(d)

    if not dirs:
        return

    existing = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = ":".join(dirs + ([existing] if existing else []))
    import sys

    os.execv(sys.executable, [sys.executable] + sys.argv)


_ensure_nvidia_lib_path()

from fastapi import FastAPI, WebSocket  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from pipecat.pipeline.base_task import PipelineTaskParams  # noqa: E402
from pipecat.pipeline.pipeline import Pipeline  # noqa: E402
from pipecat.pipeline.task import PipelineParams, PipelineTask  # noqa: E402
from pipecat.processors.aggregators.llm_context import LLMContext  # noqa: E402
from pipecat.processors.aggregators.llm_response_universal import (  # noqa: E402
    LLMContextAggregatorPair,
)
from pipecat.services.openai.llm import OpenAILLMService  # noqa: E402
from pipecat.services.piper.tts import PiperTTSService  # noqa: E402
from pipecat.services.whisper.stt import Model as WhisperModel  # noqa: E402
from pipecat.services.whisper.stt import WhisperSTTService  # noqa: E402
from pipecat.transcriptions.language import Language  # noqa: E402
from pipecat.audio.vad.silero import SileroVADAnalyzer  # noqa: E402
from pipecat.transports.websocket.fastapi import (  # noqa: E402
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

import mcp_client  # noqa: E402
from comprende_serializer import ComprendeSerializer  # noqa: E402
from session_interceptor import SessionInterceptor, TranscriptionObserver  # noqa: E402
from session_manager import SessionManager  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# CONFIG
# ============================================

LLAMA_SERVER_URL = os.getenv("LLAMA_SERVER_URL", "http://localhost:8081/v1")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "Llama-3.2-3B-Instruct-Q8_0.gguf")
PIPER_MODEL_PATH = os.getenv(
    "PIPER_MODEL_PATH", os.path.expanduser("~/piper_models/es_ES-carlfm-x_low.onnx")
)
LEARNER_ID = os.getenv("LEARNER_ID", "default_learner")

# Warmup state — server is up but not ready until models are warm
_ready = False


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ready
    await warmup()
    _ready = True
    logger.info("Server ready")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# SHARED SERVICES (initialized once, reused across connections)
# ============================================

logger.info("Loading Pipecat services...")

stt_service = WhisperSTTService(
    model=WhisperModel.MEDIUM,
    device="cuda",
    compute_type="float16",
    no_speech_prob=0.6,
    language=Language.ES,
)
logger.info("  Whisper STT ready")

llm_service = OpenAILLMService(
    model=LLAMA_MODEL,
    base_url=LLAMA_SERVER_URL,
    api_key="not-needed",
    params=OpenAILLMService.InputParams(
        temperature=0.7,
        top_p=0.9,
        max_completion_tokens=150,
    ),
)
logger.info("  LLM service ready (%s)", LLAMA_SERVER_URL)

tts_service = PiperTTSService(
    voice_id="es_ES-carlfm-x_low",
    download_dir=Path(PIPER_MODEL_PATH).parent,
)
logger.info("  Piper TTS ready")

logger.info("All Pipecat services loaded!")

# Global session manager (single learner for now)
session_manager = SessionManager(LEARNER_ID)


# ============================================
# REST ENDPOINTS (copied from voice_agent_server.py)
# ============================================


@app.post("/session/start")
async def start_session(body: dict | None = None):
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
    summary = await session_manager.end_session()
    return {"status": "ok", "summary": summary}


@app.get("/session/state")
async def get_session_state():
    info = session_manager.get_session_info()
    if not info:
        return {"status": "no_session"}
    return {"status": "ok", **info}


@app.get("/learner/profile")
async def get_learner_profile():
    profile = await mcp_client.get_learner_profile(LEARNER_ID)
    return profile


@app.get("/learner/state")
async def get_learner_state(concept_ids: str | None = None):
    ids = concept_ids.split(",") if concept_ids else None
    states = await mcp_client.get_learner_state(LEARNER_ID, concept_ids=ids)
    return states


@app.get("/learner/confusions")
async def get_learner_confusions():
    pairs = await mcp_client.get_confusion_pairs(LEARNER_ID)
    return pairs


@app.get("/learner/contexts")
async def get_learner_contexts():
    contexts = await mcp_client.get_effective_contexts(LEARNER_ID)
    return contexts


@app.get("/health")
async def health():
    if not _ready:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={"status": "warming_up", "llm_backend": LLAMA_SERVER_URL},
        )
    return {"status": "ok", "llm_backend": LLAMA_SERVER_URL, "pipeline": "pipecat"}


# ============================================
# WEBSOCKET — Pipecat pipeline per connection
# ============================================


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected (Pipecat pipeline)")

    sm = session_manager

    # If no active session, start free mode
    if not sm.state:
        sm.start_free_session()

    # Build LLM context with system prompt
    system_prompt = sm.get_system_prompt()
    context = LLMContext(
        messages=[{"role": "system", "content": system_prompt}],
    )

    # Create context aggregator pair
    aggregators = LLMContextAggregatorPair(context)

    # Create session interceptors (two-part: observer before aggregator, main after TTS)
    interceptor = SessionInterceptor(
        session_manager=sm,
        context=context,
    )
    transcription_observer = TranscriptionObserver(interceptor=interceptor)

    # Create transport with our custom serializer
    transport = FastAPIWebsocketTransport(
        websocket,
        FastAPIWebsocketParams(
            serializer=ComprendeSerializer(),
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
            audio_in_channels=1,
            audio_out_channels=1,
            vad_analyzer=SileroVADAnalyzer(sample_rate=16000),
        ),
    )

    # Send session_plan if structured mode (before pipeline starts)
    if sm.state and sm.state.mode == "structured" and sm.state.plan:
        await websocket.send_text(
            json.dumps({"type": "session_plan", "plan": sm.state.plan})
        )

    # Build the pipeline
    # TranscriptionObserver sits between STT and user aggregator to capture
    # transcription text before the aggregator consumes it.
    # SessionInterceptor sits after TTS to see LLM/TTS frames and emit metrics.
    pipeline = Pipeline(
        [
            transport.input(),
            stt_service,
            transcription_observer,
            aggregators.user(),
            llm_service,
            tts_service,
            interceptor,
            transport.output(),
            aggregators.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
        ),
    )

    @task.event_handler("on_pipeline_finished")
    async def on_finished(task, frame):
        logger.info("Pipeline finished")
        # Fire final assessment for remaining buffered turns
        if sm.state and sm.state.turn_buffer:
            await sm.end_session()

    logger.info(
        "Pipeline ready: %s",
        " → ".join(p.name for p in pipeline.processors),
    )

    try:
        await task.run(params=PipelineTaskParams(loop=asyncio.get_event_loop()))
    except Exception as e:
        logger.error("Pipeline error: %s", e, exc_info=True)
    finally:
        logger.info("Client disconnected (Pipecat pipeline)")


# ============================================
# WARMUP & MAIN
# ============================================


async def warmup():
    """Warm up LLM backend (STT/TTS warm up on first pipeline run)."""
    logger.info("Warming up LLM...")
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=LLAMA_SERVER_URL, api_key="not-needed")
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            await client.chat.completions.create(
                model=LLAMA_MODEL,
                messages=[{"role": "user", "content": "Hola"}],
                max_tokens=1,
            )
            logger.info("  LLM warm")
            break
        except Exception as e:
            if attempt == max_retries:
                logger.error(
                    "  LLM warmup failed after %d attempts: %s", max_retries, e
                )
                raise
            logger.info(
                "  LLM not ready (attempt %d/%d), retrying in 3s...",
                attempt,
                max_retries,
            )
            await asyncio.sleep(3)
    logger.info("Warmup complete!")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765)
