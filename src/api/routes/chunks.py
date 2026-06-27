"""Endpoints para la biblioteca de Mis frases (chunks)."""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from db import get_session
from models.database import Chunk
from models.schemas import ChunkResponse, ChunkSaveRequest, RecordingResponse
from repositories import RecordingRepository, SegmentsRepository, VideoRepository
from repositories.autopsy_repository import normalize_phrase
from repositories.chunk_repository import ChunkRepository
from services import recording_storage
from services.chunk_prompts import ChunkPromptsGenerationError, chunk_prompts_service

router = APIRouter(prefix="/api/chunks", tags=["chunks"])

# Tope blando de subida — generoso para una toma de una frase a bitrate opus (021).
MAX_RECORDING_BYTES = 10 * 1024 * 1024


@router.post("", response_model=ChunkResponse, status_code=201)
def save_chunk(body: ChunkSaveRequest, db: Session = Depends(get_session)):
    """Guarda una frase como chunk: la sirve desde caché o genera consignas con
    Claude y la persiste antes de devolverla."""
    video = VideoRepository(db).get_by_youtube_id(body.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    repo = ChunkRepository(db)
    phrase_key = normalize_phrase(body.phrase)
    cached = repo.get_by_phrase(video.id, phrase_key)
    if cached:
        return repo.to_response(cached)

    context = SegmentsRepository(db).context_around(video.id, body.start_time)
    if not context:
        context = [video.transcript]

    try:
        prompts = chunk_prompts_service.generate(body.phrase, context)
    except ChunkPromptsGenerationError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Generación de consignas fallida: {exc}",
        ) from exc

    row = repo.create(video.id, body.phrase, body.start_time, prompts)
    return repo.to_response(row)


@router.get("", response_model=List[ChunkResponse])
def list_chunks(db: Session = Depends(get_session)):
    """Lista todos los chunks guardados, más reciente primero."""
    repo = ChunkRepository(db)
    return [repo.to_response(row) for row in repo.list_all()]


@router.delete("/{chunk_id}", status_code=204)
def delete_chunk(chunk_id: int, db: Session = Depends(get_session)):
    """Elimina un chunk (y su grabación, fila + archivo). 404 si no existe."""
    # Borra el archivo de audio antes de tumbar el chunk; la fila `recordings`
    # se va sola por el cascade, pero el archivo en disco hay que quitarlo a mano.
    recording = RecordingRepository(db).get_by_chunk_id(chunk_id)
    if recording is not None:
        recording_storage.remove(recording.file_path)

    if not ChunkRepository(db).delete(chunk_id):
        raise HTTPException(status_code=404, detail="Chunk no encontrado")
    return Response(status_code=204)


@router.post(
    "/{chunk_id}/recording",
    response_model=RecordingResponse,
    status_code=201,
)
async def upload_recording(
    chunk_id: int,
    file: UploadFile = File(...),
    duration_seconds: Optional[float] = Form(default=None),
    db: Session = Depends(get_session),
):
    """Sube (o sobrescribe) la grabación de un chunk. Una por chunk."""
    chunk = db.get(Chunk, chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk no encontrado")

    data = await file.read()
    if len(data) > MAX_RECORDING_BYTES:
        raise HTTPException(status_code=413, detail="Grabación demasiado grande")

    repo = RecordingRepository(db)
    existing = repo.get_by_chunk_id(chunk_id)
    if existing is not None:
        recording_storage.remove(existing.file_path)

    content_type = file.content_type or "application/octet-stream"
    file_path = recording_storage.write(content_type, data)
    row = repo.upsert(chunk_id, file_path, content_type, len(data), duration_seconds)
    return repo.to_response(row)


@router.get("/{chunk_id}/recording")
def get_recording(chunk_id: int, db: Session = Depends(get_session)):
    """Sirve el audio guardado del chunk. 404 si no hay grabación."""
    row = RecordingRepository(db).get_by_chunk_id(chunk_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Grabación no encontrada")
    # no-store: a re-record overwrites at the same URL, so the browser must never
    # serve a cached take (FileResponse otherwise sets only etag/last-modified).
    return FileResponse(
        recording_storage.abs_path(row.file_path),
        media_type=row.content_type,
        headers={"Cache-Control": "no-store"},
    )


@router.delete("/{chunk_id}/recording", status_code=204)
def delete_recording(chunk_id: int, db: Session = Depends(get_session)):
    """Borra la grabación de un chunk (fila + archivo). 404 si no existe."""
    repo = RecordingRepository(db)
    row = repo.get_by_chunk_id(chunk_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Grabación no encontrada")
    recording_storage.remove(row.file_path)
    repo.delete(chunk_id)
    return Response(status_code=204)
