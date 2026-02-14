import asyncio
import websockets
import numpy as np
import json
import sounddevice as sd
import wave


async def test_with_mic():
    """Graba del micrófono y envía al servidor"""
    uri = "ws://localhost:8765/ws/voice"

    print("🔌 Conectando al servidor...")
    async with websockets.connect(uri) as websocket:
        print("✅ Conectado!")

        # Grabar audio del micrófono
        print("\n🎤 Habla ahora (3 segundos)...")
        duration = 3  # segundos
        sample_rate = 16000

        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype=np.int16
        )
        sd.wait()
        print("✅ Grabación completada")

        # Enviar audio
        print("📤 Enviando audio al servidor...")
        await websocket.send(audio.tobytes())

        # Recibir respuesta
        print("⏳ Esperando respuesta...")
        response_audio = await websocket.recv()
        metrics_json = await websocket.recv()

        metrics = json.loads(metrics_json)

        print("\n" + "=" * 60)
        print("📊 RESULTADOS:")
        print("=" * 60)
        print(f"Tu dijiste: {metrics.get('transcription', 'N/A')}")
        print(f"Respuesta:  {metrics.get('response', 'N/A')}")
        print("\n⏱️  LATENCIAS:")
        data = metrics["data"]
        print(f"  STT:   {data['stt_ms']}ms")
        print(f"  LLM:   {data['llm_ms']}ms")
        print(f"  TTS:   {data['tts_ms']}ms")
        print(f"  TOTAL: {data['total_ms']}ms")
        print("=" * 60)

        # Reproducir respuesta
        print("\n🔊 Reproduciendo respuesta...")
        audio_np = np.frombuffer(response_audio, dtype=np.int16)
        sd.play(audio_np, sample_rate)
        sd.wait()

        # Guardar para inspección
        with wave.open("response.wav", "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(response_audio)
        print("💾 Audio guardado en response.wav")


if __name__ == "__main__":
    # Instalar: pip install sounddevice
    asyncio.run(test_with_mic())
