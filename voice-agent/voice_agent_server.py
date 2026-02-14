import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import json
from datetime import datetime
import torch
from faster_whisper import WhisperModel
from vllm import LLM, SamplingParams
import subprocess
import tempfile
import os

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
# CARGAR MODELOS
# ============================================

logger.info("🔧 Cargando modelos...")


# vLLM con optimizaciones
logger.info("  - Cargando Llama 3.2-3B...")
llm_model = LLM(
    model="meta-llama/Llama-3.2-3B-Instruct",
    gpu_memory_utilization=0.5,
    dtype="half",
    max_model_len=512,  # Contexto corto
    enforce_eager=False,
    trust_remote_code=True
)

# Whisper
logger.info("  - Cargando Whisper...")
whisper_model = WhisperModel(
    "small",  # Better accuracy than base for Spanish
    device="cuda",
    compute_type="float16"
)
logger.info("  ✅ Whisper cargado")

sampling_params = SamplingParams(
    temperature=0.7,
    top_p=0.9,
    max_tokens=30,  # Respuestas cortas
    stop=["<|eot_id|>", "\n\n", "Usuario:", "<|end"]
)
logger.info("  ✅ Llama 3.2-3B cargado")

# Piper TTS
PIPER_MODEL_PATH = os.path.expanduser("~/piper_models/es_ES-carlfm-x_low.onnx")
logger.info(f"  - Piper TTS: {PIPER_MODEL_PATH}")
logger.info("✅ Todos los modelos listos!")


# ============================================
# FUNCIONES
# ============================================

async def transcribe_audio(audio_bytes):
    """STT con timeout"""
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


async def generate_response(user_text):
    """LLM con prompt limpio"""

    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

Eres un profesor de español. Responde con UNA sola frase corta y natural.<|eot_id|><|start_header_id|>user<|end_header_id|>

{user_text}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""

    def _generate():
        outputs = llm_model.generate([prompt], sampling_params)
        response = outputs[0].outputs[0].text.strip()

        # Limpiar
        response = response.split('\n')[0].split('<|')[0].strip()

        # Limitar longitud
        if len(response) > 150:
            response = response[:150].rsplit(' ', 1)[0] + "..."

        return response

    return await asyncio.to_thread(_generate)


async def text_to_speech(text):
    """TTS con fallback"""

    if not text or len(text) < 2:
        return np.zeros(8000, dtype=np.int16).tobytes()

    text = text[:200]  # Limitar

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        process = await asyncio.create_subprocess_exec(
            "piper",
            '--model', PIPER_MODEL_PATH,
            '--output_file', tmp_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=text.encode('utf-8')),
            timeout=5.0  # Timeout de 5s
        )

        if process.returncode != 0:
            raise Exception(f"Piper error: {stderr.decode()}")

        import wave
        with wave.open(tmp_path, 'rb') as wf:
            audio_data = wf.readframes(wf.getnframes())

        return audio_data

    except Exception as e:
        logger.error(f"❌ TTS error: {e}")
        # Fallback: beep simple
        t = np.linspace(0, 0.3, 4800)
        beep = (np.sin(2 * np.pi * 440 * t) * 8000).astype(np.int16)
        return beep.tobytes()

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


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
    logger.info("✅ Cliente conectado")

    try:
        while True:
            data = await websocket.receive_bytes()
            logger.info(f"📥 Recibido {len(data)} bytes")

            metrics = Metrics()
            start = datetime.now()

            # STT
            stt_start = datetime.now()
            transcription = await transcribe_audio(data)
            metrics.stt_time = (datetime.now() - stt_start).total_seconds()
            logger.info(f"🎤 STT: '{transcription}' ({metrics.stt_time * 1000:.0f}ms)")

            if not transcription:
                logger.warning("⚠️ Sin transcripción")
                await websocket.send_bytes(np.zeros(8000, dtype=np.int16).tobytes())
                continue

            # LLM
            llm_start = datetime.now()
            response_text = await generate_response(transcription)
            metrics.llm_time = (datetime.now() - llm_start).total_seconds()
            logger.info(f"🤖 LLM: '{response_text}' ({metrics.llm_time * 1000:.0f}ms)")

            # TTS
            tts_start = datetime.now()
            audio_response = await text_to_speech(response_text)
            metrics.tts_time = (datetime.now() - tts_start).total_seconds()
            logger.info(f"🔊 TTS: {len(audio_response)} bytes ({metrics.tts_time * 1000:.0f}ms)")

            metrics.total_time = (datetime.now() - start).total_seconds()

            # Enviar respuesta (audio primero, luego métricas)
            await websocket.send_bytes(audio_response)
            await websocket.send_text(json.dumps({
                "type": "metrics",
                "data": metrics.to_dict(),
                "transcription": transcription,
                "response": response_text
            }))

            logger.info(f"📤 TOTAL: {metrics.total_time * 1000:.0f}ms\n" + "=" * 60)

    except WebSocketDisconnect:
        logger.info("❌ Cliente desconectado")
    except Exception as e:
        logger.error(f"💥 Error: {e}", exc_info=True)


@app.get("/health")
async def health():
    return {"status": "ok", "gpu": torch.cuda.get_device_name(0)}


def warmup():
    """Warm up all models to avoid cold-start latency."""
    logger.info("🔥 Warming up models...")

    # STT warmup
    dummy_audio = np.zeros(16000, dtype=np.float32)  # 1s silence
    whisper_model.transcribe(dummy_audio, language="es")
    logger.info("  ✅ STT warm")

    # LLM warmup
    llm_model.generate(["Hola"], SamplingParams(max_tokens=1))
    logger.info("  ✅ LLM warm")

    # TTS warmup
    subprocess.run(
        ["piper", "--model", PIPER_MODEL_PATH, "--output_file", "/dev/null"],
        input=b"Hola",
        capture_output=True,
        timeout=10,
    )
    logger.info("  ✅ TTS warm")

    logger.info("✅ Warmup complete!")


if __name__ == "__main__":
    import uvicorn

    warmup()
    uvicorn.run(app, host="0.0.0.0", port=8765)