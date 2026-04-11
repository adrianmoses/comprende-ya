from typing import List

from prefect import flow, task
import os
import json

from db import get_session, get_db_session
from models.database import Question, Video, VideoSegment
from models.schemas import TimestampedQuestion
from repositories import VideoRepository, ExerciseRepository, SegmentsRepository
from services.youtube import youtube_service
from services.questions import question_service
from services.transcription import transcription_service
from services.frase_exercise_generator import FraseExerciseGeneratorService


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
        existing = video_repository.get_by_youtube_id(video_data['video_id'])
        if existing and force:
            # Actualizar influyendo h5p_content
            print(f"⚠️  Video {video_data['video_id']} ya existe en DB")

            existing.title = video_data['title']
            existing.duration = video_data['duration']
            existing.transcript = video_data['transcript']
            existing.youtube_url = video_data['url']
            existing.full_transcript_data = json.dumps(video_data.get('full_transcript_data'))

            for q in existing.questions:
                db.delete(q)

            for q_data in video_data['questions']:
                question = Question(
                    video_id=existing.id,
                    timestamp=q_data['timestamp'],
                    question=q_data['question'],
                    answers=json.dumps(q_data['answers']),
                    correct_answer=q_data['correct_answer'],
                    explanation=q_data.get('explanation')
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
                youtube_id=video_data['video_id'],
                youtube_url=video_data['url'],
                title=video_data['title'],
                duration=video_data['duration'],
                transcript=video_data['transcript'],
                questions=[TimestampedQuestion(**q) for q in video_data['questions']],
                full_transcript_data=video_data.get('full_transcript_data')
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
        print(f'    - {q.timestamp:.1f}s: {q.question[:50]}...')

    # 4. Guardar en DB
    video_data = {
        "video_id": metadata['video_id'],
        "title": metadata['title'],
        "duration": metadata['duration'],
        "url": video_url,
        "transcript": detailed_transcript.full_text,
        "questions": [q.dict() for q in questions],
        "full_transcript_data": detailed_transcript.dict()
    }
    db_id = save_to_database(video_data, force)

    # Guardar Video Segmentos
    save_video_segments(db_id)

    # Generar ejercicios de fill-in-the-blank
    exercises = generate_exercises_task(db_id, "medio")
    print(f"✅ {len(exercises)} ejercicios de fill-in-the-blank generados")

    # Guardar ejercicios en DB
    save_exercises_task(db_id, exercises)

    # 5. Cleanup
    cleanup(audio_path)
    print(f"🧹 Archivos temporales eliminados")

    return {
        "id": db_id,
        "video_id": metadata['video_id'],
        "title": metadata['title'],
        "duration": metadata['duration'],
        "url": video_url,
        "transcript": detailed_transcript.full_text,
        "questions": [q.dict() for q in questions],
        "exercise_count": len(exercises)
    }

