"""Endpoints para la biblioteca de Mis frases (chunks)."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session

from db import get_session
from models.schemas import ChunkResponse, ChunkSaveRequest
from repositories import SegmentsRepository, VideoRepository
from repositories.autopsy_repository import normalize_phrase
from repositories.chunk_repository import ChunkRepository
from services.chunk_prompts import ChunkPromptsGenerationError, chunk_prompts_service

router = APIRouter(prefix="/api/chunks", tags=["chunks"])


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
    """Elimina un chunk. 404 si no existe."""
    if not ChunkRepository(db).delete(chunk_id):
        raise HTTPException(status_code=404, detail="Chunk no encontrado")
    return Response(status_code=204)
