import asyncio
import logging
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_response import (
    LLMAssistantResponseAggregator,
    LLMUserResponseAggregator
)
from pipecat.services.ai_services import AIService
from pipecat.frames.frames import TextFrame, AudioRawFrame
import numpy as np

# Logging para debug
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Por ahora, servicios mock para probar la pipeline
class MockSTTService(AIService):
    """Mock STT - devuelve texto de prueba"""
    async def run_stt(self, audio: AudioRawFrame) -> TextFrame:
        logger.info("🎤 STT recibió audio")
        return TextFrame(text="Hola, ¿cómo estás?")

class MockLLMService(AIService):
    """Mock LLM - respuesta simple"""
    async def process_frame(self, frame):
        if isinstance(frame, TextFrame):
            logger.info(f"🤖 LLM recibió: {frame.text}")
            response = f"Respuesta del modelo a: {frame.text}"
            yield TextFrame(text=response)
        else:
            yield frame

class MockTTSService(AIService):
    """Mock TTS - genera audio dummy"""
    async def run_tts(self, text: str) -> AudioRawFrame:
        logger.info(f"🔊 TTS generando audio para: {text}")
        # Audio dummy (silencio de 1 segundo)
        audio_data = np.zeros(16000, dtype=np.int16)  # 1s @ 16kHz
        return AudioRawFrame(
            audio=audio_data.tobytes(),
            sample_rate=16000,
            num_channels=1
        )

async def main():
    """Prueba básica de la pipeline"""
    logger.info("🚀 Iniciando voice agent local...")
    
    # Crear servicios
    stt = MockSTTService()
    llm = MockLLMService()
    tts = MockTTSService()
    
    # Construir pipeline
    pipeline = Pipeline([
        stt,
        LLMUserResponseAggregator(),
        llm,
        LLMAssistantResponseAggregator(),
        tts
    ])
    
    # Ejecutar
    task = PipelineTask(pipeline)
    
    # Simular input de audio
    logger.info("✅ Pipeline creada, probando flujo...")
    await task.queue_frames([
        AudioRawFrame(
            audio=np.zeros(16000, dtype=np.int16).tobytes(),
            sample_rate=16000,
            num_channels=1
        )
    ])
    
    await asyncio.sleep(2)  # Dar tiempo para procesar
    logger.info("✅ Test completado!")

if __name__ == "__main__":
    asyncio.run(main())
