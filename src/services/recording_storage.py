"""Lado del sistema de archivos para las grabaciones de Mis frases (021).

Las rutas se generan en el servidor (nombre uuid + extensión derivada del
content-type), nunca a partir de entrada del usuario, así que son seguras frente
a path-traversal por construcción. Las rutas guardadas en la tabla `recordings`
son relativas a `settings.RECORDINGS_DIR`."""

from __future__ import annotations

import os
import uuid

from config import settings

# content-type (sin parámetros) → extensión de archivo. MediaRecorder emite
# audio/webm en Chrome y audio/mp4 en Safari; el resto es por si acaso.
_EXT_BY_TYPE = {
    "audio/webm": ".webm",
    "audio/mp4": ".mp4",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


def _ext_for(content_type: str) -> str:
    base = content_type.split(";", 1)[0].strip().lower()
    return _EXT_BY_TYPE.get(base, ".bin")


def write(content_type: str, data: bytes) -> str:
    """Escribe los bytes bajo RECORDINGS_DIR con un nombre no adivinable.

    Devuelve la ruta relativa a guardar en la fila `recordings`."""
    os.makedirs(settings.RECORDINGS_DIR, exist_ok=True)
    name = f"{uuid.uuid4().hex}{_ext_for(content_type)}"
    abs_path = os.path.join(settings.RECORDINGS_DIR, name)
    with open(abs_path, "wb") as fh:
        fh.write(data)
    return name


def abs_path(file_path: str) -> str:
    """Resuelve una ruta relativa guardada a su ruta absoluta para servirla."""
    return os.path.join(settings.RECORDINGS_DIR, file_path)


def remove(file_path: str) -> None:
    """Borra el archivo si existe. Idempotente — no falla si ya no está."""
    try:
        os.remove(abs_path(file_path))
    except FileNotFoundError:
        pass
