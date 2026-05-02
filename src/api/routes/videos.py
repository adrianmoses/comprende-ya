import json
import os
import re
import uuid
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import Session, select

from db import get_db_session, get_session
from flows.video_processing import process_video_flow
from models.database import Question, Video, VideoSegment
from models.schemas import VideoRequest, VideoResponse
from repositories import ProcessingJobRepository, VideoRepository
from repositories.classifier_repository import ClassifierRepository
from repositories.progress_repository import ProgressRepository
from repositories.segments_repository import SegmentsRepository
from services.dialect_classifier import dialect_classifier
from services.questions import question_service
from services.transcription import transcription_service
from services.youtube import youtube_service
from services.youtube_search import youtube_search
from services.youtube_transcript import youtube_transcript_service

router = APIRouter()


async def run_flow_background(flow_run_id: str, video_url: str, force: bool = False):
    """Ejecuta el flow en background y persiste el estado en processing_jobs."""
    # Mark RUNNING. We open and close the session before running the flow so
    # we don't hold a connection from the pool across the multi-minute job.
    try:
        with get_db_session() as db:
            ProcessingJobRepository(db).mark_running(flow_run_id)
    except Exception as e:
        print(f"⚠️  Could not mark RUNNING for {flow_run_id}: {e}")

    try:
        result = process_video_flow(video_url, force=force)
        with get_db_session() as db:
            ProcessingJobRepository(db).mark_completed(
                flow_run_id,
                video_id=result.get("id") if isinstance(result, dict) else None,
            )
    except Exception as e:
        with get_db_session() as db:
            ProcessingJobRepository(db).mark_failed(flow_run_id, error=str(e))


@router.get("/search")
async def search_videos(
    query: str = Query(..., description="Búsqueda de videos de YouTube"),
    max_results: int = Query(10, ge=1, le=25, description="Número máximo de resultados"),
):
    """
    Busca videos de YouTube por query
    :param query: Término de búsqueda
    :param max_results: Número máximo de resultados (1-25)
    :return: Lista de videos con metadata
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query no puede estar vacío")

    results = youtube_search.search_videos(query, max_results)
    return {"results": results}


@router.get("/search/classify/{video_id}")
async def classify_video_from_search(video_id: str):
    """
    Clasifica el dialecto de un video específico usando su transcripción de YouTube
    :param video_id: ID del video de YouTube
    :return: Clasificación del dialecto o error si no hay transcripción
    """
    # Intentar obtener transcripción (muestra de 3000 caracteres)
    transcript_sample = youtube_transcript_service.get_transcript_sample(video_id, max_chars=3000)

    if not transcript_sample:
        raise HTTPException(
            status_code=404, detail="No se encontró transcripción disponible para este video"
        )

    # Clasificar dialecto
    classification = dialect_classifier.classify_from_sample(transcript_sample)

    if not classification:
        raise HTTPException(status_code=500, detail="Error al clasificar el dialecto del video")

    return classification


@router.post("/process-async")
async def process_video_async(
    request: VideoRequest,
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Forzar reprocesamiento aunque el video ya exista"),
    db: Session = Depends(get_session),
):
    """
    Inicia procesamiento asynchronico con Prefect
    :param request:
    :return:
    """

    # Extraer YouTube video ID de la URL
    match = re.search(r"(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&]+)", str(request.url))
    if not match:
        raise HTTPException(status_code=400, detail="URL de YouTube inválida")

    youtube_video_id = match.group(1)

    # Verificar si ya existe
    if not force:
        repo = VideoRepository(db)
        existing_video = repo.get_by_youtube_id(youtube_video_id)

        if existing_video:
            print(f"✅ Video {youtube_video_id} ya existe en DB (ID: {existing_video.id})")
            # Devolver el video existente
            return {
                "flow_run_id": None,
                "status": "EXISTS",
                "message": "Video ya procesado",
                "result": {
                    "id": existing_video.id,
                    "video_id": existing_video.youtube_id,
                    "title": existing_video.title,
                    "duration": existing_video.duration,
                    "transcript": existing_video.transcript,
                    "questions": [
                        {
                            "id": q.id,
                            "timestamp": q.timestamp,
                            "question": q.question,
                            "answers": json.loads(q.answers),
                            "correct_answer": q.correct_answer,
                            "explanation": q.explanation,
                        }
                        for q in existing_video.questions
                    ],
                    "created_at": existing_video.created_at.isoformat(),
                },
            }

    flow_run_id = str(uuid.uuid4())

    # Persistir el estado inicial del job en processing_jobs.
    ProcessingJobRepository(db).create_pending(
        flow_run_id=flow_run_id,
        youtube_url=str(request.url),
        youtube_video_id=youtube_video_id,
    )

    # Ejecutar flow en background
    background_tasks.add_task(run_flow_background, flow_run_id, str(request.url), force)

    return {
        "flow_run_id": flow_run_id,
        "status": "PENDING",
        "message": f"Video en procesamiento{' (forzado)' if force else ''}",
    }


@router.get("/status/{flow_run_id}")
async def get_flow_status(flow_run_id: str, db: Session = Depends(get_session)):
    """
    Obtiene el estado del flow desde processing_jobs.
    """
    job = ProcessingJobRepository(db).get_by_flow_run_id(flow_run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Flow no encontrado")

    response = {
        "flow_run_id": job.flow_run_id,
        "status": job.status,
        "url": job.youtube_url,
        "youtube_video_id": job.youtube_video_id,
        "video_id": job.video_id,
    }
    if job.status == "FAILED" and job.error:
        response["error"] = job.error
    return response


@router.get("/flows")
async def get_flows(
    skip: int = 0,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    """
    Lista los flows persistidos, más recientes primero.
    """
    jobs = ProcessingJobRepository(db).list(skip=skip, limit=limit)
    return {
        "flows": [
            {
                "flow_run_id": j.flow_run_id,
                "status": j.status,
                "url": j.youtube_url,
            }
            for j in jobs
        ]
    }


@router.get("/{video_id}")
async def get_video(video_id: str, db: Session = Depends(get_session)):
    """
    Obtener video procesando por ID (permalink)
    :param video_id:
    :param db:
    :return:
    """

    repo = VideoRepository(db)
    video = repo.get_by_youtube_id(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    return {
        "id": video.id,
        "video_id": video.youtube_id,
        "url": video.youtube_url,
        "title": video.title,
        "duration": video.duration,
        "transcript": video.transcript,
        "questions": [
            {
                "id": q.id,
                "timestamp": q.timestamp,
                "question": q.question,
                "answers": json.loads(q.answers),
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
            }
            for q in video.questions
        ],
        "created_at": video.created_at.isoformat(),
        "fill_in_blank_exercises": [
            {
                "id": exercise.id,
                "original_text": exercise.original_transcript_text,
                "exercise_text": exercise.exercise_text,
                "answers": json.loads(exercise.answers),
                "hints": json.loads(exercise.hints),
                "difficulty": exercise.difficulty,
                "start_time": exercise.start_time,
                "end_time": exercise.end_time,
            }
            for exercise in video.frase_exercises
        ],
    }


@router.get("/")
async def list_videos(skip: int = 0, limit: int = 20, db: Session = Depends(get_session)):
    """
    Lista todos los videos
    :param skip:
    :param limit:
    :param db:
    :return:
    """
    repo = VideoRepository(db)

    videos = repo.list(skip, limit)

    return {
        "videos": [
            {
                "id": v.id,
                "video_id": v.youtube_id,
                "title": v.title,
                "duration": v.duration,
                "questions": v.questions,
                "created_at": v.created_at.isoformat(),
            }
            for v in videos
        ]
    }


@router.get("/{video_id}/segments")
async def get_video_segments(video_id: int, session: Session = Depends(get_session)) -> List[dict]:
    """Obtiene los segmentos de transcripción de un video"""

    # Verificar que el video existe
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    # Obtener segmentos
    segments = session.exec(
        select(VideoSegment)
        .where(VideoSegment.video_id == video_id)
        .order_by(VideoSegment.segment_number)
    ).all()

    segment_repo = SegmentsRepository()
    # Si no hay segmentos, intentar extraerlos
    if not segments and video.full_transcript_data:
        segments = segment_repo.extract_and_save_segments(video, session)

    return [
        {
            "segment_number": seg.segment_number,
            "transcript": seg.transcript_text,
            "start_time": seg.start_time,
            "end_time": seg.end_time,
        }
        for seg in segments
    ]


@router.post(
    "/process",
    response_model=VideoResponse,
    responses={
        400: {"description": "Video inválido o muy largo"},
        500: {"description": "Error procesando video"},
    },
)
async def process_video(request: VideoRequest):
    """
    Procesa un video de YouTube: descarga, transcribe, genera preguntas
    :param request:
    :return:
    """

    try:
        # 1. Descarga audio a temp path
        print("Descargando")
        audio_path, metadata = youtube_service.download_audio(str(request.url))

        # 2. Transcribir
        print("Transcribando")
        transcript = transcription_service.transcribe(audio_path)

        # 3. Generar pregruntas
        print("Generando preguntas")
        questions = question_service.generate_question(transcript)

        # 4. Limpiar archivo temporal
        print("Limpiando archivo")
        os.remove(audio_path)

        print("yt metadata")
        print(metadata)

        return VideoResponse(
            video_id=metadata["video_id"],
            title=metadata["title"],
            duration=metadata["duration"],
            transcript=transcript,
            questions=questions,
        )
    except HTTPException:
        # Re-lanzar HTTPException tal cual
        raise
    except ValueError as e:
        return HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return HTTPException(status_code=500, detail=f"Error procesando video: {str(e)}")


# Progress tracking endpoints


@router.post("/{video_id}/progress")
async def save_progress(
    video_id: str, question_id: int, user_answer: int, db: Session = Depends(get_session)
):
    """
    Guarda el progreso de una respuesta.

    Args:
        video_id: YouTube ID del video
        question_id: ID de la pregunta
        user_answer: Índice de la respuesta seleccionada (0-3)
    """
    # Obtener el video por YouTube ID
    video_repo = VideoRepository(db)
    video = video_repo.get_by_youtube_id(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    # Obtener la pregunta para verificar la respuesta
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")

    if question.video_id != video.id:
        raise HTTPException(status_code=400, detail="La pregunta no pertenece a este video")

    # Verificar si la respuesta es correcta
    is_correct = user_answer == question.correct_answer

    # Guardar progreso
    progress_repo = ProgressRepository(db)
    progress = progress_repo.save_answer(
        video_id=video.id, question_id=question_id, user_answer=user_answer, is_correct=is_correct
    )

    return {
        "question_id": question_id,
        "user_answer": user_answer,
        "is_correct": is_correct,
        "answered_at": progress.answered_at.isoformat(),
    }


@router.get("/{video_id}/progress")
async def get_progress(video_id: str, db: Session = Depends(get_session)):
    """
    Obtiene el progreso de todas las preguntas de un video.

    Args:
        video_id: YouTube ID del video
    """
    # Obtener el video por YouTube ID
    video_repo = VideoRepository(db)
    video = video_repo.get_by_youtube_id(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    # Obtener progreso
    progress_repo = ProgressRepository(db)
    progress_records = progress_repo.get_video_progress(video.id)
    summary = progress_repo.get_progress_summary(video.id)

    # Formatear respuesta
    progress_data = [
        {
            "question_id": p.question_id,
            "user_answer": p.user_answer,
            "is_correct": p.is_correct,
            "answered_at": p.answered_at.isoformat(),
        }
        for p in progress_records
    ]

    return {"video_id": video_id, "summary": summary, "progress": progress_data}


@router.delete("/{video_id}/progress")
async def reset_progress(video_id: str, db: Session = Depends(get_session)):
    """
    Resetea todo el progreso de un video.

    Args:
        video_id: YouTube ID del video
    """
    # Obtener el video por YouTube ID
    video_repo = VideoRepository(db)
    video = video_repo.get_by_youtube_id(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    # Resetear progreso
    progress_repo = ProgressRepository(db)
    deleted_count = progress_repo.reset_video_progress(video.id)

    return {
        "video_id": video_id,
        "deleted_count": deleted_count,
        "message": "Progreso reseteado exitosamente",
    }


@router.get("/{video_id}/classify")
async def classify(video_id: str, db: Session = Depends(get_session)):
    # Obtener el video por YouTube ID
    video_repo = VideoRepository(db)
    video = video_repo.get_by_youtube_id(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    classifier_repo = ClassifierRepository(db)
    classified = classifier_repo.classify_video(video)

    return {"video_id": video_id, "classified": classified}
