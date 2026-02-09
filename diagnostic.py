# diagnostic.py
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import wave

print("🔍 DIAGNÓSTICO DE COMPONENTES\n")

# Test 1: Grabar y verificar audio
print("=" * 60)
print("TEST 1: CAPTURA DE AUDIO")
print("=" * 60)
print("🎤 Habla ahora (di: 'Hola, esto es una prueba') - 3 segundos...")

duration = 3
sample_rate = 16000
audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype=np.int16)
sd.wait()

audio_level = np.abs(audio).mean()
print(f"✅ Audio capturado")
print(f"   Nivel promedio: {audio_level:.2f}")
print(f"   Máximo: {np.abs(audio).max()}")
print(f"   ¿Es silencio?: {'SÍ ⚠️' if audio_level < 50 else 'NO ✅'}")

# Guardar para inspección
with wave.open("test_input.wav", "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)
    wf.writeframes(audio.tobytes())
print("   Guardado en: test_input.wav")

# Reproducir lo que grabaste
print("\n🔊 Reproduciendo lo que grabaste...")
sd.play(audio, sample_rate)
sd.wait()

# Test 2: Transcripción
print("\n" + "=" * 60)
print("TEST 2: TRANSCRIPCIÓN (WHISPER)")
print("=" * 60)
print("⏳ Transcribiendo...")

whisper_model = WhisperModel("medium", device="cuda", compute_type="float16")
audio_np = audio.flatten().astype(np.float32) / 32768.0

segments, info = whisper_model.transcribe(
    audio_np,
    language="es",
    beam_size=5,
    vad_filter=True,
    temperature=0.0
)

transcription = " ".join([segment.text for segment in segments]).strip()

print(f"✅ Transcripción: '{transcription}'")
print(f"   Idioma detectado: {info.language} (confianza: {info.language_probability:.2f})")

if not transcription:
    print("⚠️  PROBLEMA: Transcripción vacía!")
    print("   - Verifica que el micrófono esté funcionando")
    print("   - Aumenta el volumen del micrófono en pavucontrol")
    print("   - Habla más alto y claro")

# Test 3: TTS
print("\n" + "=" * 60)
print("TEST 3: TEXT-TO-SPEECH (PIPER)")
print("=" * 60)

import subprocess
import tempfile
import os

test_text = "Hola, esta es una prueba de síntesis de voz en español."
print(f"📝 Generando audio para: '{test_text}'")

PIPER_MODEL = os.path.expanduser("~/piper_models/es_ES-sharvard-medium.onnx")

with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
    tmp_path = tmp_file.name

try:
    result = subprocess.run(
        ["piper", "--model", PIPER_MODEL, "--output_file", tmp_path],
        input=test_text.encode('utf-8'),
        capture_output=True,
        timeout=5
    )

    if result.returncode != 0:
        print(f"❌ Error de Piper: {result.stderr.decode()}")
    else:
        print("✅ TTS generado")

        # Reproducir
        print("🔊 Reproduciendo TTS...")
        with wave.open(tmp_path, 'rb') as wf:
            tts_audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
            sd.play(tts_audio, wf.getframerate())
            sd.wait()

        print(f"   Guardado en: {tmp_path}")
        print(f"   Puedes reproducirlo: ffplay {tmp_path}")

except FileNotFoundError:
    print("❌ Piper no encontrado!")
    print("   Instala: pip install piper-tts")
except Exception as e:
    print(f"❌ Error: {e}")

finally:
    # No borrar para inspección
    pass

print("\n" + "=" * 60)
print("✅ DIAGNÓSTICO COMPLETADO")
print("=" * 60)