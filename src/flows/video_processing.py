import json
import os
from collections import defaultdict
from typing import List

from prefect import flow, task

from db import get_db_session
from models.database import Question, Video, VideoSegment
from models.schemas import TimestampedQuestion
from repositories import ExerciseRepository, SegmentsRepository, VideoRepository
from repositories.autopsy_repository import AutopsyRepository, normalize_phrase
from services.frase_exercise_generator import FraseExerciseGeneratorService
from services.phrase_markers import (
    MarkerEntry,
    PhraseMarkersGenerationError,
    phrase_markers_service,
)
from services.questions import question_service
from services.segment_tokenizer import tokenize_segment
from services.spanish_nlp import get_nlp
from services.transcription import transcription_service
from services.youtube import youtube_service


@task(name="Download YouTube Audio", retries=2)
def download_audio(video_url: str):
    """Descarga un archivo de audio"""
    audio_path, metadata = youtube_service.download_audio(video_url)
    return audio_path, metadata


@task(name="Transcribe Audio con Timestamps", retries=1)
def transcribe_with_timestamps(audio_path: str):
    """Transcribe audio con Whisper"""
    detailed_transcript = transcription_service.transcribe_with_timestamps(audio_path)
    return detailed_transcript


@task(name="Generar Timestamped Questions", retries=2)
def generate_timestamped_questions(detailed_transcript: str):
    """Genera preguntas con Claude"""
    questions = question_service.generate_timestamped_questions(detailed_transcript)
    return questions


@task(name="Cleanup Temporary Files")
def cleanup(audio_path: str):
    """Elimina archivo temporales"""
    if os.path.exists(audio_path):
        os.remove(audio_path)


@task(name="Save to Database")
def save_to_database(video_data: dict, force: bool = False):
    """Guardar video procesando en la base de datos"""

    with get_db_session() as db:
        video_repository = VideoRepository(db)
        existing = video_repository.get_by_youtube_id(video_data["video_id"])
        if existing and force:
            # Actualizar influyendo h5p_content
            print(f"⚠️  Video {video_data['video_id']} ya existe en DB")

            existing.title = video_data["title"]
            existing.duration = video_data["duration"]
            existing.transcript = video_data["transcript"]
            existing.youtube_url = video_data["url"]
            existing.full_transcript_data = json.dumps(video_data.get("full_transcript_data"))

            for q in existing.questions:
                db.delete(q)

            for q_data in video_data["questions"]:
                question = Question(
                    video_id=existing.id,
                    timestamp=q_data["timestamp"],
                    question=q_data["question"],
                    answers=json.dumps(q_data["answers"]),
                    correct_answer=q_data["correct_answer"],
                    explanation=q_data.get("explanation"),
                )
                db.add(question)

            db.add(existing)
            db.commit()

            print(f"✅ Video actualizado en DB con ID: {existing.id}")
            return existing.id
        elif existing and not force:
            print(f"⚠️  Video {video_data['video_id']} ya existe en DB")
            return existing.id
        else:
            # Crear nuevo
            video = video_repository.create(
                youtube_id=video_data["video_id"],
                youtube_url=video_data["url"],
                title=video_data["title"],
                duration=video_data["duration"],
                transcript=video_data["transcript"],
                questions=[TimestampedQuestion(**q) for q in video_data["questions"]],
                full_transcript_data=video_data.get("full_transcript_data"),
            )

            print(f"✅ Video guardado en DB con ID: {video.id}")
            return video.id


@task(name="Guardar Timestamp Segments", retries=2)
def save_video_segments(video_id: int) -> List[VideoSegment]:
    """Guardar video segmentos"""

    segments = []
    with get_db_session() as db:
        video = db.get(Video, video_id)
        segments_repository = SegmentsRepository(db)
        segments = segments_repository.extract_and_save_segments(video)
        print(f"Creados {len(segments)} segmentos para el video")
    return segments


@task(name="Generar Phrase Markers")
def generate_phrase_markers_task(video_id: int, segments: List[VideoSegment]) -> List[MarkerEntry]:
    """Pide a Claude marcadores de frases interesantes para todo el vídeo.

    Si la llamada o el parseo fallan por completo, devuelve [] para que el
    resto del flow continúe (los segmentos se quedan con `tokens` null y la
    caché de autopsia sin pre-poblar).
    """
    try:
        markers = phrase_markers_service.explain_video(segments)
        print(f"✅ {len(markers)} marcadores de frase generados")
        return markers
    except PhraseMarkersGenerationError as exc:
        print(f"⚠️  Generación de marcadores falló: {exc}")
        return []


@task(name="Guardar Phrase Markers")
def save_phrase_markers_task(
    video_id: int,
    segments: List[VideoSegment],
    markers: List[MarkerEntry],
) -> None:
    """Tokeniza cada segmento, guarda `tokens` y pre-puebla la caché de autopsia.

    Las filas existentes en `phrase_autopsy` (por `phrase_key`) ganan: un tap
    manual que ya pobló la caché no se sobrescribe.
    """

    if not segments:
        return

    nlp = get_nlp()
    by_segment: dict[int, list[MarkerEntry]] = defaultdict(list)
    for m in markers:
        by_segment[m["segment_number"]].append(m)

    with get_db_session() as db:
        autopsy_repo = AutopsyRepository(db)
        for seg in segments:
            seg_markers = by_segment.get(seg.segment_number, [])
            span_phrases = [(i, m["tokens_in_segment"]) for i, m in enumerate(seg_markers)]
            tokens = tokenize_segment(seg.transcript_text, span_phrases, nlp)

            db_seg = db.get(VideoSegment, seg.id)
            if db_seg is None:
                continue
            db_seg.tokens = json.dumps(tokens, ensure_ascii=False)
            db.add(db_seg)

            for m in seg_markers:
                phrase_key = normalize_phrase(m["phrase"])
                if autopsy_repo.get_by_phrase(video_id, phrase_key):
                    continue
                autopsy_repo.create(
                    video_id=video_id,
                    phrase=m["phrase"],
                    start_time=seg.start_time,
                    payload={
                        "register": m["register"],
                        "grammar": m["grammar"],
                        "natural_notes": m["natural_notes"],
                    },
                )
        db.commit()


@task(name="Generar Exercises", retries=2)
def generate_exercises_task(video_id: int, difficulty: str):
    """Genera ejercicios de fill-in-the-blank para un video"""
    with get_db_session() as db:
        segments_repository = SegmentsRepository(db)
        video_segments = segments_repository.get_by_video_id(video_id)
        generator = FraseExerciseGeneratorService(difficulty)
        return generator.generate_exercises_from_transcription(video_segments)


@task(name="Guardar Frase Ejercicios", retries=2)
def save_exercises_task(video_id: int, exercises: List[dict]):
    """Guarda ejercicios de fill-in-the-blank en la base de datos"""
    with get_db_session() as db:
        exercise_repo = ExerciseRepository(db)
        created_exercises = exercise_repo.create_exercises(video_id, exercises)
        print(f"✅ {len(created_exercises)} ejercicios guardados en DB")
        return created_exercises


@flow(name="Process Video", log_prints=True)
def process_video_flow(video_url: str, force: bool = False):
    """
    Flow principal para procesar videos de YouTube
    :param video_url:
    :return:
    """

    print(f"🎬 Iniciando procesamiento: {video_url}{' (FORZADO)' if force else ''}")

    # 1. Descargar
    audio_path, metadata = download_audio(video_url)
    print(f"✅ Audio descargado: {metadata['title']}")

    # 2. Transcribe con timestamps
    detailed_transcript = transcribe_with_timestamps(audio_path)
    print(f"✅ Transcripción completa: {len(detailed_transcript.segments)} caracteres")

    # 3. Generar preguntas
    questions = generate_timestamped_questions(detailed_transcript)
    print(f"✅ {len(questions)} preguntas generadas con timestamps")
    for q in questions:
        print(f"    - {q.timestamp:.1f}s: {q.question[:50]}...")

    # 4. Guardar en DB
    video_data = {
        "video_id": metadata["video_id"],
        "title": metadata["title"],
        "duration": metadata["duration"],
        "url": video_url,
        "transcript": detailed_transcript.full_text,
        "questions": [q.dict() for q in questions],
        "full_transcript_data": detailed_transcript.dict(),
    }
    db_id = save_to_database(video_data, force)

    # Guardar Video Segmentos
    segments = save_video_segments(db_id)

    # Generar marcadores de frase y pre-poblar caché de autopsia (018)
    markers = generate_phrase_markers_task(db_id, segments)
    save_phrase_markers_task(db_id, segments, markers)

    # Generar ejercicios de fill-in-the-blank
    exercises = generate_exercises_task(db_id, "medio")
    print(f"✅ {len(exercises)} ejercicios de fill-in-the-blank generados")

    # Guardar ejercicios en DB
    save_exercises_task(db_id, exercises)

    # 5. Cleanup
    cleanup(audio_path)
    print("🧹 Archivos temporales eliminados")

    return {
        "id": db_id,
        "video_id": metadata["video_id"],
        "title": metadata["title"],
        "duration": metadata["duration"],
        "url": video_url,
        "transcript": detailed_transcript.full_text,
        "questions": [q.dict() for q in questions],
        "exercise_count": len(exercises),
    }
